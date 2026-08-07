import os
import numpy as np
import tifffile
from typing import List
from PIL import Image, ImageDraw
from core import layout_engine
from core import tiff_parser
from core.models import Project

def compile_sheet_pass(
    project: Project, 
    target_pass: str, 
    ppi: int, 
    validation_reports: List[dict] = None
) -> np.ndarray:
    """
    Compiles a full print sheet canvas for a specific print pass at the specified PPI.
    Assigns cards to slots, scales/rotates them, and pastes them onto a high-res page canvas.
    """
    active_profile = project.export_settings.get("active_printer_profile", "Default")
    from core import print_validation
    profiles = print_validation.load_printer_profiles()
    p_data = profiles.get(active_profile, {"scale_x": 100.0, "scale_y": 100.0})
    scale_x = p_data.get("scale_x", 100.0) / 100.0
    scale_y = p_data.get("scale_y", 100.0) / 100.0

    grid = layout_engine.calculate_layout_positions(
        project.layout, ppi, 
        compensation_x=scale_x, compensation_y=scale_y
    )
    page_w = grid["page_width"]
    page_h = grid["page_height"]

    # 1. Initialize empty sheet canvas and registration mark ink values
    if target_pass == "Base Artwork":
        # White background RGBA canvas
        sheet_arr = np.full((page_h, page_w, 4), 255, dtype=np.uint8)
    else:
        # The page background outside the card slots must ALWAYS be WHITE (value 255)
        bg_val = 255
        if target_pass == "White Ink":
            ink_val = 0  # Registration marks are BLACK (value 0)
        elif target_pass == "Emboss":
            ink_val = 255  # Registration marks are WHITE (value 255) / invisible
        else:
            # Default fallback (e.g. Gloss)
            ink_val = 0
            
        sheet_arr = np.full((page_h, page_w), bg_val, dtype=np.uint8)

    debug_enabled = project.export_settings.get("binary_debug", False)
    from core.dithering import validate_binary_channel

    # 2. Render cards into their respective slots
    for slot_def in grid["slots"]:
        s_idx = slot_def["index"]
        slot_state = project.card_slots[s_idx]
        
        # Skip if no TIFF is loaded in this slot
        if not slot_state.filepath or not os.path.exists(slot_state.filepath):
            continue

        try:
            channels = tiff_parser.parse_tiff_channels(slot_state.filepath)
            h_card, w_card = slot_def["height"], slot_def["width"]
            sx, sy = slot_def["x"], slot_def["y"]

            if target_pass == "Base Artwork":
                # Find channels mapped to Base Artwork (R, G, B, A)
                art_ch = {}
                rgb_target = slot_state.mappings.get("Base Artwork (RGB)", "Base Artwork")
                if "Base Artwork (RGB)" not in slot_state.disabled_channels and rgb_target == "Base Artwork":
                    for ch in channels:
                        if slot_state.disabled_channels and ch.name in slot_state.disabled_channels:
                            continue
                        name_lower = ch.name.lower()
                        if "red" in name_lower or (not art_ch and ch.channel_in_page == 0):
                            art_ch['R'] = ch
                        elif "green" in name_lower or (len(art_ch) == 1 and ch.channel_in_page == 1):
                            art_ch['G'] = ch
                        elif "blue" in name_lower or (len(art_ch) == 2 and ch.channel_in_page == 2):
                            art_ch['B'] = ch
                        elif "alpha" in name_lower or "transparency" in name_lower:
                            art_ch['A'] = ch

                card_img = Image.new("RGBA", (w_card, h_card), (255, 255, 255, 255))
                if 'R' in art_ch or 'G' in art_ch or 'B' in art_ch:
                    r_arr = tiff_parser.load_channel_array(slot_state.filepath, art_ch['R']) if 'R' in art_ch else np.full(channels[0].shape, 255, dtype=np.uint8)
                    g_arr = tiff_parser.load_channel_array(slot_state.filepath, art_ch['G']) if 'G' in art_ch else np.full(channels[0].shape, 255, dtype=np.uint8)
                    b_arr = tiff_parser.load_channel_array(slot_state.filepath, art_ch['B']) if 'B' in art_ch else np.full(channels[0].shape, 255, dtype=np.uint8)
                    a_arr = tiff_parser.load_channel_array(slot_state.filepath, art_ch['A']) if 'A' in art_ch else np.full(channels[0].shape, 255, dtype=np.uint8)
                    
                    orig_card_img = Image.fromarray(np.stack([r_arr, g_arr, b_arr, a_arr], axis=-1), mode="RGBA")
                    card_img = orig_card_img.resize((w_card, h_card), Image.Resampling.LANCZOS)

                # Rotate card
                if slot_state.rotation != 0:
                    card_img = card_img.rotate(360 - slot_state.rotation, expand=False, fillcolor=(255, 255, 255, 0))

                # Paste into sheet canvas using PIL alpha pasting
                sheet_img = Image.fromarray(sheet_arr, mode="RGBA")
                sheet_img.paste(card_img, (sx, sy), card_img)
                sheet_arr = np.array(sheet_img)

            else:
                # Find channel mapped to this custom print pass (White Ink, Gloss, Emboss, etc.)
                target_ch = None
                for ch in channels:
                    if slot_state.disabled_channels and ch.name in slot_state.disabled_channels:
                        continue
                    mapped = slot_state.mappings.get(ch.name)
                    if mapped == target_pass:
                        target_ch = ch
                        break

                if target_ch:
                    raw_spot = tiff_parser.load_channel_array(slot_state.filepath, target_ch)
                    
                    # Audit Stage: Original Loaded
                    if debug_enabled and validation_reports is not None:
                        raw_report = validate_binary_channel(raw_spot, target_pass, f"Slot {s_idx} - Original Loaded")
                        validation_reports.append(raw_report)
                        
                    spot_img = Image.fromarray(raw_spot, mode="L")
                    # Use NEAREST resampling to preserve binary pixel bounds and prevent anti-aliasing
                    spot_img_resized = spot_img.resize((w_card, h_card), Image.Resampling.NEAREST)
                    spot_arr = np.array(spot_img_resized)
                    
                    # Shape validation check
                    if spot_arr.shape != (h_card, w_card):
                        raise ValueError(
                            f"Spot channel shape mismatch in stage 'Resize' for pass '{target_pass}': "
                            f"expected {(h_card, w_card)}, got {spot_arr.shape}"
                        )
                        
                    # Audit Stage: Resized
                    if debug_enabled and validation_reports is not None:
                        resize_report = validate_binary_channel(spot_arr, target_pass, f"Slot {s_idx} - Resized")
                        validation_reports.append(resize_report)
                    
                    if target_pass == "White Ink":
                        dither_settings = slot_state.dither_settings
                        dither_mode = dither_settings.get("dither_mode")
                        if dither_mode is None:
                            enabled = dither_settings.get("dither_enabled", "false") == "true"
                            dither_mode = dither_settings.get("dither_algo", "Ordered Bayer") if enabled else "None"
                            
                        coverage_str = dither_settings.get("dither_coverage")
                        if coverage_str is None:
                            strength = int(dither_settings.get("dither_strength", "15"))
                            dither_coverage = str(100 - strength)
                        else:
                            dither_coverage = coverage_str
                            
                        settings = {
                            "dither_coverage": dither_coverage,
                            "dither_angle": dither_settings.get("dither_angle", "45.0"),
                            "dither_lpi": dither_settings.get("dither_lpi", "45.0"),
                            "dither_dot_shape": dither_settings.get("dither_dot_shape", "Round"),
                        }
                        
                        from core import dithering
                        spot_arr = dithering.process_white_channel(spot_arr, dither_mode, float(ppi), settings)
                        
                        # Shape validation check
                        if spot_arr.shape != (h_card, w_card):
                            raise ValueError(
                                f"Spot channel shape mismatch in stage 'Mask Generation' for pass '{target_pass}': "
                                f"expected {(h_card, w_card)}, got {spot_arr.shape}"
                            )
                            
                        # Audit Stage: Mask Generated
                        if debug_enabled and validation_reports is not None:
                            gen_report = validate_binary_channel(spot_arr, target_pass, f"Slot {s_idx} - Mask Generated")
                            validation_reports.append(gen_report)
                        
                        # Composition stage: Duplicate Emboss Into White
                        if dither_settings.get("dither_duplicate_emboss") == "true":
                            emboss_ch = None
                            for ch in channels:
                                if slot_state.disabled_channels and ch.name in slot_state.disabled_channels:
                                    continue
                                mapped = slot_state.mappings.get(ch.name)
                                if mapped == "Emboss":
                                    emboss_ch = ch
                                    break
                            if emboss_ch:
                                raw_emboss = tiff_parser.load_channel_array(slot_state.filepath, emboss_ch)
                                emboss_img = Image.fromarray(raw_emboss, mode="L")
                                # Use NEAREST resampling to keep emboss mask binary
                                emboss_img_resized = emboss_img.resize((w_card, h_card), Image.Resampling.NEAREST)
                                emboss_arr = np.array(emboss_img_resized)
                                
                                # Shape validation check
                                if emboss_arr.shape != (h_card, w_card):
                                    raise ValueError(
                                        f"Spot channel shape mismatch in stage 'Emboss Resize' for pass 'Emboss': "
                                        f"expected {(h_card, w_card)}, got {emboss_arr.shape}"
                                    )
                                    
                                spot_arr = dithering.compose_white_channel(spot_arr, emboss_arr, dither_settings)
                                
                                # Shape validation check
                                if spot_arr.shape != (h_card, w_card):
                                    raise ValueError(
                                        f"Spot channel shape mismatch in stage 'Composition' for pass '{target_pass}': "
                                        f"expected {(h_card, w_card)}, got {spot_arr.shape}"
                                    )
                                    
                                # Audit Stage: Composed
                                if debug_enabled and validation_reports is not None:
                                    comp_report = validate_binary_channel(spot_arr, target_pass, f"Slot {s_idx} - Composed")
                                    validation_reports.append(comp_report)
                            
                    spot_img_resized = Image.fromarray(spot_arr, mode="L")
                    if slot_state.rotation != 0:
                        # Use NEAREST resampling for rotation to keep spot channel borders binary
                        spot_img_resized = spot_img_resized.rotate(
                            360 - slot_state.rotation, 
                            expand=False, 
                            fillcolor=bg_val, 
                            resample=Image.Resampling.NEAREST
                        )
                        spot_arr = np.array(spot_img_resized)
                        
                        # Shape validation check
                        if spot_arr.shape != (h_card, w_card):
                            raise ValueError(
                                f"Spot channel shape mismatch in stage 'Rotate' for pass '{target_pass}': "
                                f"expected {(h_card, w_card)}, got {spot_arr.shape}"
                            )
                            
                        # Audit Stage: Rotated
                        if debug_enabled and validation_reports is not None:
                            rot_report = validate_binary_channel(spot_arr, target_pass, f"Slot {s_idx} - Rotated")
                            validation_reports.append(rot_report)
                        
                    sheet_arr[sy:sy+h_card, sx:sx+w_card] = spot_arr
        except Exception as e:
            print(f"Error compiling slot {s_idx} for pass '{target_pass}': {e}")

    # 3. Draw registration marks on top
    reg_mask = layout_engine.draw_registration_marks(project.layout, ppi)
    reg_arr = np.array(reg_mask)
    mask = reg_arr[..., 3] > 0

    if target_pass == "Base Artwork":
        # Draw registration marks in solid black on RGB layer
        sheet_arr[mask, 0:3] = 0
        sheet_arr[mask, 3] = 255
    else:
        # Draw registration marks in solid ink color
        sheet_arr[mask] = ink_val

    return sheet_arr

def create_photoshop_resource_block(channel_names: List[str]) -> bytes:
    """Encodes custom spot channel names into Photoshop Image Resource block format (ID 1006)."""
    data_bytes = bytearray()
    for name in channel_names:
        name_bytes = name.encode('utf-8', errors='ignore')[:255]
        data_bytes.append(len(name_bytes))
        data_bytes.extend(name_bytes)
    if len(data_bytes) % 2 != 0:
        data_bytes.append(0)
    
    resource_id = 1006
    block = bytearray(b'8BIM')
    block.extend(resource_id.to_bytes(2, 'big'))
    block.extend(b'\x00\x00') # Empty name Pascal string
    block.extend(len(data_bytes).to_bytes(4, 'big'))
    block.extend(data_bytes)
    return bytes(block)

def export_project(project: Project, output_path: str, export_type: str, ppi: int = 600) -> tuple:
    """
    Main export dispatcher.
    Arguments:
        project: Project data model
        output_path: Target absolute output filepath/directory
        export_type: 'layered_tiff', 'flat_tiff', 'pdf_preview', 'png_preview'
        ppi: Target printing resolution (default 600 PPI)
    Returns:
        tuple of (output_path, validation_reports)
    """
    validation_reports = []
    failed_passes = []
    
    debug_enabled = project.export_settings.get("binary_debug", False)
    from core.dithering import validate_binary_channel, binary_enforce_channel

    active_profile = project.export_settings.get("active_printer_profile", "Default")
    from core import print_validation
    profiles = print_validation.load_printer_profiles()
    p_data = profiles.get(active_profile, {"scale_x": 100.0, "scale_y": 100.0})
    scale_x = p_data.get("scale_x", 100.0) / 100.0
    scale_y = p_data.get("scale_y", 100.0) / 100.0

    if export_type == "layered_tiff":
        # 1. Filter enabled and mapped passes
        enabled_passes = [p for p in project.print_passes if p not in project.disabled_passes]
        active_spot_passes = []
        for pass_name in enabled_passes:
            if pass_name == "Base Artwork":
                continue
            
            # Check if mapped and enabled in any slot
            is_mapped = False
            for slot in project.card_slots:
                if slot.filepath:
                    for ch_name, target in slot.mappings.items():
                        if target == pass_name and ch_name not in slot.disabled_channels:
                            is_mapped = True
                            break
                    if is_mapped:
                        break
            if is_mapped:
                active_spot_passes.append(pass_name)

        # 2. Print Export Summary Logs
        print("\n========================================")
        print("             EXPORT SUMMARY             ")
        print("========================================")
        for pass_name in project.print_passes:
            status = "Enabled" if pass_name not in project.disabled_passes else "Disabled"
            if pass_name != "Base Artwork" and pass_name not in active_spot_passes and status == "Enabled":
                status = "Enabled (Unmapped - Excluded)"
            print(f"\n{pass_name} ({status})")
            
            if status.startswith("Enabled"):
                for slot in project.card_slots:
                    if slot.filepath:
                        mapped_ch = []
                        for ch_name, target in slot.mappings.items():
                            if target == pass_name and ch_name not in slot.disabled_channels:
                                mapped_ch.append(ch_name)
                        if mapped_ch:
                            print(f"  - Card Slot {slot.slot_index} ({os.path.basename(slot.filepath)}):")
                            for ch in mapped_ch:
                                print(f"    * {ch}")
                                
        is_base_enabled = "Base Artwork" in enabled_passes
        output_order = []
        if is_base_enabled:
            output_order.append("Base Artwork (RGB)")
        for pass_name in active_spot_passes:
            output_order.append(pass_name)
            
        for idx, name in enumerate(output_order):
            print(f"  {idx + 1}. {name}")
        print("========================================\n")

        print("Writing output TIFF...")
        
        channels_list = []
        preserve_orig = project.export_settings.get("preserve_channel_names", "true") == "true"
        
        if is_base_enabled:
            print("Writing RGB (Base Artwork)...")
            art_arr = compile_sheet_pass(project, "Base Artwork", ppi, validation_reports)
            rgb_arr = art_arr[..., 0:3] # Extract RGB
            channels_list.extend([rgb_arr[..., 0], rgb_arr[..., 1], rgb_arr[..., 2]])
            
        # 1. Find the first card slot containing a TIFF file to get original spot channel names and order
        ref_slot = None
        for slot in project.card_slots:
            if slot.filepath and os.path.exists(slot.filepath):
                ref_slot = slot
                break
                
        # 2. Extract spot channels from the reference slot in their exact original order
        ref_spot_channels = []
        if ref_slot:
            try:
                ref_all_channels = tiff_parser.parse_tiff_channels(ref_slot.filepath)
                # Determine if the file is PSD-structured
                is_psd_structured = any(ch.page_index == -1 for ch in ref_all_channels)
                
                for ch in ref_all_channels:
                    name_lower = ch.name.lower()
                    is_rgb = "red" in name_lower or "green" in name_lower or "blue" in name_lower or (ch.page_index == 0 and ch.channel_in_page in (0, 1, 2))
                    if is_rgb:
                        continue
                    
                    if is_psd_structured:
                        if ch.page_index != -1:
                            continue
                    else:
                        if ch.page_index <= 0:
                            continue
                        if "alpha" in name_lower or "transparency" in name_lower:
                            continue
                            
                    ref_spot_channels.append(ch)
            except Exception as e:
                print(f"Error reading spot channels from reference card: {e}")
                
        # 3. Compile and stack channels in the exact order of ref_spot_channels
        extra_names = []
        for ref_ch in ref_spot_channels:
            # Check what print pass is mapped to this original channel name in the reference slot
            target_pass = ref_slot.mappings.get(ref_ch.name) if ref_slot else None
            
            # The name to write in the Photoshop spot channel metadata
            name_to_write = ref_ch.name if preserve_orig else target_pass
            extra_names.append(name_to_write)
            
            # Compile sheet for this print pass if it is enabled in the project,
            # otherwise write a blank white canvas to preserve the channel structure/count
            is_pass_enabled = target_pass and target_pass in project.print_passes and target_pass not in project.disabled_passes
            
            grid = layout_engine.calculate_layout_positions(
                project.layout, ppi, 
                compensation_x=scale_x, compensation_y=scale_y
            )
            page_w = grid["page_width"]
            page_h = grid["page_height"]
            
            if is_pass_enabled:
                print(f"Writing Spot Channel ({name_to_write}) mapped from pass {target_pass}...")
                pass_arr = compile_sheet_pass(project, target_pass, ppi, validation_reports)
                
                # Shape Validation
                expected_shape = (page_h, page_w)
                if pass_arr.shape != expected_shape:
                    raise ValueError(
                        f"Spot channel shape mismatch in stage 'Sheet Composition' for pass '{target_pass}': "
                        f"expected {expected_shape}, got {pass_arr.shape}"
                    )
                    
                # Audit Stage: Sheet Composition
                if debug_enabled:
                    sheet_report = validate_binary_channel(pass_arr, target_pass, "Sheet Composition")
                    validation_reports.append(sheet_report)
                    
                # Final gate validation (Validate -> Auto-Repair -> Re-Validate)
                report_before = validate_binary_channel(pass_arr, target_pass, "Final TIFF Assembly (Before Repair)")
                
                validation_mode = project.export_settings.get("validation_mode", "auto_repair")
                
                if not report_before["pass"]:
                    if validation_mode == "strict":
                        failed_passes.append(report_before)
                    elif validation_mode == "auto_repair":
                        pass_arr = binary_enforce_channel(pass_arr)
                        report_before["repaired"] = True
                        
                        # Re-validate
                        report_after = validate_binary_channel(pass_arr, target_pass, "Final TIFF Assembly (After Repair)")
                        if not report_after["pass"]:
                            raise ValueError(
                                f"CRITICAL: Final gate validation failed after repair on pass '{target_pass}'! "
                                f"Repaired unique values: {report_after['unique_values']}"
                            )
                        if debug_enabled:
                            validation_reports.append(report_after)
                    else: # "report_only"
                        pass
                        
                if debug_enabled or not report_before["pass"]:
                    validation_reports.append(report_before)
                    
                channels_list.append(pass_arr)
            else:
                print(f"Writing Blank Spot Channel ({name_to_write}) - Pass disabled or unmapped...")
                blank_arr = np.full((page_h, page_w), 255, dtype=np.uint8)
                channels_list.append(blank_arr)
                
        if not is_base_enabled:
            # If base artwork is disabled, extra spot channel names for Photoshop tag start from index 1
            extra_names = extra_names[1:] if len(extra_names) > 1 else []
            
        if not channels_list:
            raise ValueError("No active print passes to export! Please enable and map at least one print pass.")
            
        # Final gate validation pass over all compiled spot channels in channels_list
        spot_idx_offset = 3 if is_base_enabled else 0
        for spot_idx, ref_ch in enumerate(ref_spot_channels):
            target_pass_name = ref_slot.mappings.get(ref_ch.name) if ref_slot else None
            is_p_enabled = target_pass_name and target_pass_name in project.print_passes and target_pass_name not in project.disabled_passes
            if is_p_enabled:
                pass_arr_final = channels_list[spot_idx_offset + spot_idx]
                
                # Double check shape
                expected_shape = (page_h, page_w)
                if pass_arr_final.shape != expected_shape:
                    raise ValueError(
                        f"Spot channel shape mismatch in final assembled TIFF for pass '{target_pass_name}': "
                        f"expected {expected_shape}, got {pass_arr_final.shape}"
                    )
                    
                final_report = validate_binary_channel(pass_arr_final, target_pass_name, "TIFF Write Gatekeeper")
                if not final_report["pass"]:
                    raise ValueError(
                        f"CRITICAL: Final TIFF Write Gatekeeper check failed on pass '{target_pass_name}'! "
                        f"Values to be written contain invalid grayscale/dtype: {final_report['invalid_values']}"
                    )
                if debug_enabled:
                    validation_reports.append(final_report)

        # Handle collected failures under strict validation mode
        if failed_passes and validation_mode == "strict":
            err_msg = "Strict validation failed for the following spot passes:\n"
            for fail in failed_passes:
                err_msg += f"- Pass '{fail['pass_name']}' in stage '{fail['stage_name']}': invalid values {fail['invalid_values']}\n"
            raise ValueError(err_msg)

        # Determine stack dimensions and photometric interpretation
        if len(channels_list) == 1:
            stacked_arr = channels_list[0]
            photometric = 'minisblack'
        else:
            stacked_arr = np.stack(channels_list, axis=-1)
            photometric = 'rgb' if is_base_enabled else 'minisblack'

        total_ch = stacked_arr.shape[-1] if len(stacked_arr.shape) == 3 else 1
        base_ch = 3 if photometric == 'rgb' else 1
        num_extra = max(0, total_ch - base_ch)

        if num_extra > 0:
            if photometric == 'rgb':
                extra_samples = [2] + [0] * (num_extra - 1)
                all_extra_names = ["Alpha"] + extra_names[:num_extra - 1]
            else:
                extra_samples = [0] * num_extra
                all_extra_names = extra_names[:num_extra]
        else:
            extra_samples = None
            all_extra_names = []

        extratags = []
        if all_extra_names:
            resource_bytes = create_photoshop_resource_block(all_extra_names)
            extratags.append((34377, 1, len(resource_bytes), resource_bytes, True))

        # Embed calibration metadata in ImageDescription tag (tag 270, ASCII type = 2)
        import datetime
        meta_desc = (
            f"Prepress Card App Calibration Metadata\n"
            f"Target Card Size: {project.layout.card_size.width_mm:.2f}x{project.layout.card_size.height_mm:.2f} mm\n"
            f"Bleed: {project.layout.bleed_mm:.2f} mm\n"
            f"PPI: {ppi}\n"
            f"Active Printer Profile: {active_profile}\n"
            f"Compensation Scale X: {scale_x * 100.0:.2f}%\n"
            f"Compensation Scale Y: {scale_y * 100.0:.2f}%\n"
            f"Creation Date: {datetime.datetime.now().isoformat()}\n"
            f"Application Version: 1.0.0"
        )
        desc_bytes = (meta_desc + "\0").encode('utf-8')
        extratags.append((270, 2, len(desc_bytes), desc_bytes, True))
            
        tifffile.imwrite(
            output_path,
            stacked_arr,
            photometric=photometric,
            extrasamples=extra_samples,
            extratags=extratags,
            metadata={'axes': 'YXS' if len(stacked_arr.shape) == 3 else 'YX'}
        )
        print("Export complete.\n")
        return output_path, validation_reports

    elif export_type == "flat_tiff":
        # Output only the Base Artwork page as a single page TIFF
        art_arr = compile_sheet_pass(project, "Base Artwork", ppi, validation_reports)
        # Drop alpha channel for standard RGB flattened print
        rgb_arr = art_arr[..., 0:3]
        tifffile.imwrite(output_path, rgb_arr, metadata={'axes': 'YXS'})
        return output_path, []

    elif export_type == "png_preview":
        # Save Base Artwork as a quick PNG
        art_arr = compile_sheet_pass(project, "Base Artwork", ppi, validation_reports)
        img = Image.fromarray(art_arr, mode="RGBA")
        img.save(output_path, "PNG")
        return output_path, []

    elif export_type == "pdf_preview":
        # Generate PDF of the artwork page
        art_arr = compile_sheet_pass(project, "Base Artwork", ppi, validation_reports)
        img = Image.fromarray(art_arr, mode="RGBA").convert("RGB")
        img.save(output_path, format="PDF", resolution=ppi)
        return output_path, []

    else:
        raise ValueError(f"Unknown export type: {export_type}")


def create_card_corner_mask(w_px: int, h_px: int, radius_mm: float, ppi: int) -> np.ndarray:
    """
    Generates a 2D uint8 mask array (0 or 255) for a card with rounded corners.
    Inside card: 255 (active card area)
    Outside corners: 0 (outside card shape)
    """
    r_px = max(1, round((radius_mm / 25.4) * ppi))
    mask_img = Image.new("L", (w_px, h_px), 0)
    draw = ImageDraw.Draw(mask_img)
    draw.rounded_rectangle([0, 0, w_px - 1, h_px - 1], radius=r_px, fill=255)
    return np.array(mask_img, dtype=np.uint8)


def export_individual_cards(project: Project, output_dir: str, ppi: int = 600) -> tuple:
    """
    Exports each configured card slot in the project as a standalone prepress layered TIFF file
    at target PPI (600 PPI), cropped to standard card dimensions (63x88 mm, 3mm corner radius).
    Returns:
        tuple of (exported_file_paths, validation_reports)
    """
    import tifffile
    os.makedirs(output_dir, exist_ok=True)
    exported_paths = []
    all_reports = []
    
    from core.dithering import binary_enforce_channel
    
    w_card_mm = project.layout.card_size.width_mm
    h_card_mm = project.layout.card_size.height_mm
    radius_mm = project.layout.card_size.radius_mm
    w_px = round((w_card_mm / 25.4) * ppi)
    h_px = round((h_card_mm / 25.4) * ppi)
    
    # Generate single shared 63x88mm 3mm rounded corner mask
    corner_mask = create_card_corner_mask(w_px, h_px, radius_mm, ppi)
    outside_corners = (corner_mask == 0)

    for slot in project.card_slots:
        if not slot.filepath or not os.path.exists(slot.filepath):
            continue
            
        base_name = os.path.splitext(os.path.basename(slot.filepath))[0]
        out_filename = f"card_slot_{slot.slot_index + 1}_{base_name}_600ppi.tiff"
        out_path = os.path.join(output_dir, out_filename)
        
        channels = tiff_parser.parse_tiff_channels(slot.filepath)
        
        # Determine active passes for this slot
        enabled_passes = [p for p in project.print_passes if p not in project.disabled_passes]
        active_spot_passes = []
        for pass_name in enabled_passes:
            if pass_name == "Base Artwork":
                continue
            for ch_name, target in slot.mappings.items():
                if target == pass_name and ch_name not in slot.disabled_channels:
                    active_spot_passes.append(pass_name)
                    break

        channels_list = []
        extra_names = []
        is_base_enabled = "Base Artwork" in enabled_passes

        # Render Base Artwork (RGBA with true Alpha=0 transparency outside 3mm corners)
        if is_base_enabled:
            art_ch = {}
            rgb_target = slot.mappings.get("Base Artwork (RGB)", "Base Artwork")
            if "Base Artwork (RGB)" not in slot.disabled_channels and rgb_target == "Base Artwork":
                for ch in channels:
                    if slot.disabled_channels and ch.name in slot.disabled_channels:
                        continue
                    name_lower = ch.name.lower()
                    if "red" in name_lower or (not art_ch and ch.channel_in_page == 0):
                        art_ch['R'] = ch
                    elif "green" in name_lower or (len(art_ch) == 1 and ch.channel_in_page == 1):
                        art_ch['G'] = ch
                    elif "blue" in name_lower or (len(art_ch) == 2 and ch.channel_in_page == 2):
                        art_ch['B'] = ch
                    elif "alpha" in name_lower or "transparency" in name_lower:
                        art_ch['A'] = ch

            if 'R' in art_ch or 'G' in art_ch or 'B' in art_ch:
                r_arr = tiff_parser.load_channel_array(slot.filepath, art_ch['R']) if 'R' in art_ch else np.full(channels[0].shape, 255, dtype=np.uint8)
                g_arr = tiff_parser.load_channel_array(slot.filepath, art_ch['G']) if 'G' in art_ch else np.full(channels[0].shape, 255, dtype=np.uint8)
                b_arr = tiff_parser.load_channel_array(slot.filepath, art_ch['B']) if 'B' in art_ch else np.full(channels[0].shape, 255, dtype=np.uint8)
                a_arr = tiff_parser.load_channel_array(slot.filepath, art_ch['A']) if 'A' in art_ch else np.full(channels[0].shape, 255, dtype=np.uint8)
                orig = Image.fromarray(np.stack([r_arr, g_arr, b_arr, a_arr], axis=-1), mode="RGBA")
                card_img = orig.resize((w_px, h_px), Image.Resampling.LANCZOS)
            else:
                card_img = Image.new("RGBA", (w_px, h_px), (255, 255, 255, 255))

            if slot.rotation != 0:
                card_img = card_img.rotate(360 - slot.rotation, expand=False, fillcolor=(255, 255, 255, 0))

            card_arr = np.array(card_img)
            
            # Mask 4 corners outside rounded rectangle to Alpha = 0 (True Transparency for Photoshop)
            card_arr[outside_corners, 3] = 0

            # Append 4 RGBA channels (Red, Green, Blue, Alpha)
            channels_list.append(card_arr[..., 0])
            channels_list.append(card_arr[..., 1])
            channels_list.append(card_arr[..., 2])
            channels_list.append(card_arr[..., 3])

        # Render Spot Passes
        for pass_name in active_spot_passes:
            target_ch = None
            for ch in channels:
                if slot.disabled_channels and ch.name in slot.disabled_channels:
                    continue
                if slot.mappings.get(ch.name) == pass_name:
                    target_ch = ch
                    break

            if target_ch:
                raw_spot = tiff_parser.load_channel_array(slot.filepath, target_ch)
                spot_img = Image.fromarray(raw_spot, mode="L")
                spot_img_resized = spot_img.resize((w_px, h_px), Image.Resampling.NEAREST)
                spot_arr = np.array(spot_img_resized)

                from core import dithering

                # Dithering ONLY applies to White Ink (never to Emboss or Gloss)
                if pass_name == "White Ink":
                    dither_mode = slot.dither_settings.get("dither_mode", "None")
                    spot_arr = dithering.process_white_channel(spot_arr, dither_mode, ppi, slot.dither_settings)

                    # Duplicate Emboss Into White Ink channel
                    if slot.dither_settings.get("dither_duplicate_emboss") == "true":
                        emboss_ch = None
                        for ch in channels:
                            if slot.disabled_channels and ch.name in slot.disabled_channels:
                                continue
                            if slot.mappings.get(ch.name) == "Emboss":
                                emboss_ch = ch
                                break
                        if emboss_ch:
                            raw_emboss = tiff_parser.load_channel_array(slot.filepath, emboss_ch)
                            emboss_img = Image.fromarray(raw_emboss, mode="L").resize((w_px, h_px), Image.Resampling.NEAREST)
                            emboss_arr = np.array(emboss_img)
                            spot_arr = dithering.compose_white_channel(spot_arr, emboss_arr, slot.dither_settings)

                # Rotate spot channel if slot is rotated
                if slot.rotation != 0:
                    spot_img_rot = Image.fromarray(spot_arr, mode="L").rotate(
                        360 - slot.rotation, expand=False, fillcolor=255, resample=Image.Resampling.NEAREST
                    )
                    spot_arr = np.array(spot_img_rot)

                # Mask 4 corners outside rounded rectangle to pure white (255 = 0% ink / no spot ink)
                spot_arr[outside_corners] = 255

                repaired_arr = dithering.binary_enforce_channel(spot_arr)
                rep = dithering.validate_binary_channel(repaired_arr, pass_name, f"Slot {slot.slot_index + 1} - Final")
                all_reports.append(rep)
                channels_list.append(repaired_arr)
                
                # Spot channel naming
                ch_display_name = pass_name
                if pass_name == "White Ink":
                    ch_display_name = "1"
                elif pass_name == "Emboss":
                    ch_display_name = "3"
                extra_names.append(ch_display_name)

        if not channels_list:
            continue

        if len(channels_list) == 1:
            stacked_arr = channels_list[0]
            photometric = 'minisblack'
        else:
            stacked_arr = np.stack(channels_list, axis=-1)
            photometric = 'rgb' if is_base_enabled else 'minisblack'
        
        total_ch = stacked_arr.shape[-1] if len(stacked_arr.shape) == 3 else 1
        base_ch = 3 if photometric == 'rgb' else 1
        num_extra = max(0, total_ch - base_ch)

        if num_extra > 0:
            if photometric == 'rgb':
                extra_samples = [2] + [0] * (num_extra - 1)
                all_extra_names = ["Alpha"] + extra_names[:num_extra - 1]
            else:
                extra_samples = [0] * num_extra
                all_extra_names = extra_names[:num_extra]
        else:
            extra_samples = None
            all_extra_names = []

        extratags = []
        if all_extra_names:
            resource_bytes = create_photoshop_resource_block(all_extra_names)
            extratags.append((34377, 1, len(resource_bytes), resource_bytes, True))

        tifffile.imwrite(
            out_path,
            stacked_arr,
            photometric=photometric,
            extrasamples=extra_samples,
            extratags=extratags,
            metadata={'axes': 'YXS' if len(stacked_arr.shape) == 3 else 'YX'}
        )
        exported_paths.append(out_path)

    return exported_paths, all_reports


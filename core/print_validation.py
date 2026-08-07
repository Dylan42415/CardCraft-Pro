import os
import datetime
import numpy as np
from typing import Tuple, List, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont
from core import tiff_parser

class PhysicalSize:
    def __init__(self, width_mm: float, height_mm: float, width_in: float, height_in: float):
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.width_inches = width_in
        self.height_inches = height_in

def calculate_physical_size(pixel_width: int, pixel_height: int, ppi: float) -> PhysicalSize:
    """
    Converts pixel dimensions and PPI resolution to physical sizes in millimeters and inches.
    Formula: mm = pixels / ppi * 25.4
    """
    if ppi <= 0:
        ppi = 300.0
    width_in = pixel_width / ppi
    height_in = pixel_height / ppi
    width_mm = width_in * 25.4
    height_mm = height_in * 25.4
    return PhysicalSize(width_mm, height_mm, width_in, height_in)

def validate_print_dimensions(project, slot_index: int, tolerance_mm: float = 0.05) -> dict:
    """
    Checks if the slot's TIFF file actual physical size matches the expected size (card size + bleed).
    Returns a dictionary with validation results.
    """
    slot = project.card_slots[slot_index]
    if not slot.filepath or not os.path.exists(slot.filepath):
        return {"pass": True, "warnings": [], "msg": "No file loaded"}

    try:
        channels = tiff_parser.parse_tiff_channels(slot.filepath)
        if not channels:
            return {"pass": False, "warnings": ["Could not parse channels from TIFF file."], "msg": "Invalid channels"}
        
        pixel_width = channels[0].shape[1]
        pixel_height = channels[0].shape[0]
        file_ppi = tiff_parser.get_tiff_ppi(slot.filepath)
        
        # Calculate actual physical size of the loaded TIFF
        actual_size = calculate_physical_size(pixel_width, pixel_height, file_ppi)
        
        # Expected size is card size plus 2 * bleed
        bleed_mm = project.layout.bleed_mm
        expected_w_mm = project.layout.card_size.width_mm + 2 * bleed_mm
        expected_h_mm = project.layout.card_size.height_mm + 2 * bleed_mm
        
        diff_w = actual_size.width_mm - expected_w_mm
        diff_h = actual_size.height_mm - expected_h_mm
        
        w_ok = abs(diff_w) <= tolerance_mm
        h_ok = abs(diff_h) <= tolerance_mm
        passed = w_ok and h_ok
        
        expected_ratio = expected_w_mm / expected_h_mm
        actual_ratio = actual_size.width_mm / actual_size.height_mm
        ratio_ok = abs(expected_ratio - actual_ratio) <= 0.01
        
        warnings = []
        if not w_ok or not h_ok:
            warnings.append(
                f"Export dimensions differ from target size.\n"
                f"Expected: {expected_w_mm:.2f} × {expected_h_mm:.2f} mm\n"
                f"Actual: {actual_size.width_mm:.2f} × {actual_size.height_mm:.2f} mm\n"
                f"Tolerance: ±{tolerance_mm:.2f} mm"
            )
        if not ratio_ok:
            warnings.append(f"Aspect ratio mismatch. Expected {expected_ratio:.3f}, got {actual_ratio:.3f}")
            
        return {
            "pass": passed,
            "filepath": slot.filepath,
            "pixel_width": pixel_width,
            "pixel_height": pixel_height,
            "ppi": file_ppi,
            "actual_w_mm": actual_size.width_mm,
            "actual_h_mm": actual_size.height_mm,
            "expected_w_mm": expected_w_mm,
            "expected_h_mm": expected_h_mm,
            "diff_w_mm": diff_w,
            "diff_h_mm": diff_h,
            "warnings": warnings
        }
    except Exception as e:
        return {"pass": False, "warnings": [f"Error reading image measurements: {e}"], "msg": str(e)}

def build_validation_report(project, tolerance_mm: float = 0.05) -> dict:
    """
    Compiles a comprehensive print validation report for all populated slots.
    """
    report = {
        "pass": True,
        "slots": {},
        "overall_warnings": []
    }
    
    for slot in project.card_slots:
        if slot.filepath and os.path.exists(slot.filepath):
            slot_res = validate_print_dimensions(project, slot.slot_index, tolerance_mm)
            report["slots"][slot.slot_index] = slot_res
            if not slot_res.get("pass", True):
                report["pass"] = False
                report["overall_warnings"].extend(slot_res.get("warnings", []))
                
    return report

def generate_calibration_sheet(project, output_path: str, ppi: int = 300) -> str:
    """
    Generates a printable A4 PDF sheet at 300 PPI containing calibration guides,
    rulers, alignment lines, and step-by-step instructions.
    """
    # A4 Dimensions: 210mm x 297mm
    page_w = round((210.0 / 25.4) * ppi)
    page_h = round((297.0 / 25.4) * ppi)
    
    # 1. Initialize blank white image canvas
    img = Image.new("RGB", (page_w, page_h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # 2. Draw A4 border safety line
    border_inset = round((5.0 / 25.4) * ppi)
    draw.rectangle([border_inset, border_inset, page_w - border_inset, page_h - border_inset], outline=(200, 200, 200), width=1)
    
    # 3. Render Card outlines in the upper part
    card_w_mm = project.layout.card_size.width_mm
    card_h_mm = project.layout.card_size.height_mm
    bleed_mm = project.layout.bleed_mm
    
    card_w_px = round((card_w_mm / 25.4) * ppi)
    card_h_px = round((card_h_mm / 25.4) * ppi)
    bleed_px = round((bleed_mm / 25.4) * ppi)
    
    center_x = page_w // 2
    center_y = page_h // 3  # Place card outline in upper third
    
    # Card outer bleed outline
    outer_w = card_w_px + 2 * bleed_px
    outer_h = card_h_px + 2 * bleed_px
    ox1 = center_x - outer_w // 2
    oy1 = center_y - outer_h // 2
    ox2 = ox1 + outer_w
    oy2 = oy1 + outer_h
    
    # Inner cutline (actual card size)
    ix1 = center_x - card_w_px // 2
    iy1 = center_y - card_h_px // 2
    ix2 = ix1 + card_w_px
    iy2 = iy1 + card_h_px
    
    # Draw outer bleed dashed boundary (drawn as alternating dots or solid grey line)
    draw.rectangle([ox1, oy1, ox2, oy2], outline=(150, 150, 150), width=2)
    # Draw inner cutline boundary
    draw.rectangle([ix1, iy1, ix2, iy2], outline=(0, 0, 0), width=2)
    
    # 4. Draw Crop Marks at inner cutline corners
    mark_len = round((8.0 / 25.4) * ppi)
    # Top-Left corner crop marks
    draw.line([(ix1 - mark_len, iy1), (ix1 - 2, iy1)], fill=(0, 0, 0), width=2)
    draw.line([(ix1, iy1 - mark_len), (ix1, iy1 - 2)], fill=(0, 0, 0), width=2)
    # Top-Right
    draw.line([(ix2 + 2, iy1), (ix2 + mark_len, iy1)], fill=(0, 0, 0), width=2)
    draw.line([(ix2, iy1 - mark_len), (ix2, iy1 - 2)], fill=(0, 0, 0), width=2)
    # Bottom-Left
    draw.line([(ix1 - mark_len, iy2), (ix1 - 2, iy2)], fill=(0, 0, 0), width=2)
    draw.line([(ix1, iy2 + 2), (ix1, iy2 + mark_len)], fill=(0, 0, 0), width=2)
    # Bottom-Right
    draw.line([(ix2 + 2, iy2), (ix2 + mark_len, iy2)], fill=(0, 0, 0), width=2)
    draw.line([(ix2, iy2 + 2), (ix2, iy2 + mark_len)], fill=(0, 0, 0), width=2)
    
    # 5. Draw 10mm Calibration Square
    sq_size = round((10.0 / 25.4) * ppi)
    sq_x1 = round((30.0 / 25.4) * ppi)
    sq_y1 = page_h - round((95.0 / 25.4) * ppi)
    sq_x2 = sq_x1 + sq_size
    sq_y2 = sq_y1 + sq_size
    draw.rectangle([sq_x1, sq_y1, sq_x2, sq_y2], outline=(0, 0, 0), fill=(240, 240, 240), width=2)
    
    # Draw crosshair inside the calibration square
    sq_cx = (sq_x1 + sq_x2) // 2
    sq_cy = (sq_y1 + sq_y2) // 2
    draw.line([(sq_x1, sq_cy), (sq_x2, sq_cy)], fill=(120, 120, 120), width=1)
    draw.line([(sq_cx, sq_y1), (sq_cx, sq_y2)], fill=(120, 120, 120), width=1)
    
    # 6. Draw Horizontal and Vertical Millimeter Rulers (0 to 50 mm)
    # Horizontal Ruler
    hr_x1 = sq_x2 + round((20.0 / 25.4) * ppi)
    hr_y1 = sq_y1 + sq_size // 2
    hr_w = round((50.0 / 25.4) * ppi)
    draw.line([(hr_x1, hr_y1), (hr_x1 + hr_w, hr_y1)], fill=(0, 0, 0), width=2)
    
    for i in range(51):
        tick_x = hr_x1 + round((i / 25.4) * ppi)
        if i % 10 == 0:
            tick_len = round((5.0 / 25.4) * ppi)
        elif i % 5 == 0:
            tick_len = round((3.5 / 25.4) * ppi)
        else:
            tick_len = round((2.0 / 25.4) * ppi)
        draw.line([(tick_x, hr_y1), (tick_x, hr_y1 - tick_len)], fill=(0, 0, 0), width=2)
        
    # Vertical Ruler
    vr_x1 = sq_x1 + sq_size // 2
    vr_y1 = sq_y2 + round((20.0 / 25.4) * ppi)
    vr_h = round((50.0 / 25.4) * ppi)
    draw.line([(vr_x1, vr_y1), (vr_x1, vr_y1 + vr_h)], fill=(0, 0, 0), width=2)
    
    for i in range(51):
        tick_y = vr_y1 + round((i / 25.4) * ppi)
        if i % 10 == 0:
            tick_len = round((5.0 / 25.4) * ppi)
        elif i % 5 == 0:
            tick_len = round((3.5 / 25.4) * ppi)
        else:
            tick_len = round((2.0 / 25.4) * ppi)
        draw.line([(vr_x1, tick_y), (vr_x1 - tick_len, tick_y)], fill=(0, 0, 0), width=2)
        
    # 7. Add Labels and Step-by-Step Instructions
    # Try loading default font; PIL text drawing fallback is always safe
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
        
    def draw_text_helper(text: str, xy: Tuple[int, int], fill=(0, 0, 0)):
        draw.text(xy, text, fill=fill, font=font)
        
    # Calibration Square Text
    draw_text_helper("10x10 mm SQUARE", (sq_x1 - 10, sq_y1 - 25))
    draw_text_helper("Measure square precisely with caliper.", (sq_x1, sq_y2 + 5))
    
    # Ruler Labels
    draw_text_helper("50 mm Horizontal Ruler", (hr_x1 + 10, hr_y1 + 10))
    for i in (0, 10, 20, 30, 40, 50):
        tick_x = hr_x1 + round((i / 25.4) * ppi)
        draw_text_helper(f"{i}", (tick_x - 4, hr_y1 - 22))
        
    draw_text_helper("50 mm", (vr_x1 + 10, vr_y1 + 10))
    draw_text_helper("Vertical", (vr_x1 + 10, vr_y1 + 25))
    draw_text_helper("Ruler", (vr_x1 + 10, vr_y1 + 40))
    for i in (0, 10, 20, 30, 40, 50):
        tick_y = vr_y1 + round((i / 25.4) * ppi)
        draw_text_helper(f"{i}", (vr_x1 - 32, tick_y - 6))

    # General Page Title & Template info
    title_y = round((20.0 / 25.4) * ppi)
    draw_text_helper("PROFESSIONAL PRINT CALIBRATION SHEET", (round((30.0 / 25.4) * ppi), title_y))
    draw_text_helper(f"Active Card Layout: {project.layout.name}", (round((30.0 / 25.4) * ppi), title_y + 20))
    draw_text_helper(f"Target Card Size: {card_w_mm:.2f} × {card_h_mm:.2f} mm", (round((30.0 / 25.4) * ppi), title_y + 40))
    draw_text_helper(f"Bleed Settings: {bleed_mm:.2f} mm", (round((30.0 / 25.4) * ppi), title_y + 60))
    draw_text_helper(f"Export Target PPI: {ppi} PPI", (round((30.0 / 25.4) * ppi), title_y + 80))
    draw_text_helper(f"Page Canvas Resolution: {page_w} × {page_h} pixels", (round((30.0 / 25.4) * ppi), title_y + 100))
    
    # Instruction Block
    inst_x = page_w - round((100.0 / 25.4) * ppi)
    inst_y = page_h - round((95.0 / 25.4) * ppi)
    
    draw_text_helper("PRINTING INSTRUCTIONS", (inst_x, inst_y), fill=(220, 50, 50))
    draw_text_helper("1. Print this sheet at exactly 100% SCALE.", (inst_x, inst_y + 20))
    draw_text_helper("2. DISABLE scaling features in printer driver:", (inst_x, inst_y + 40))
    draw_text_helper("   • Disable 'Fit to Page'", (inst_x, inst_y + 60))
    draw_text_helper("   • Disable 'Scale to Fit'", (inst_x, inst_y + 80))
    draw_text_helper("   • Disable 'Shrink Oversized Pages'", (inst_x, inst_y + 100))
    draw_text_helper("3. Measure the 10x10 mm Square with a caliper.", (inst_x, inst_y + 120))
    draw_text_helper("4. Use Calibration Wizard to input measured sizes.", (inst_x, inst_y + 140))
    
    # Save image as PDF directly
    img.save(output_path, "PDF", resolution=float(ppi))
    return output_path

import json

def get_profiles_file_path() -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_dir = os.path.join(base_dir, "data", "config")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "printer_calibration_profiles.json")

def load_printer_profiles() -> Dict[str, dict]:
    filepath = get_profiles_file_path()
    if not os.path.exists(filepath):
        # Seed default profiles
        default_profiles = {
            "Default": {
                "scale_x": 100.0,
                "scale_y": 100.0,
                "date_calibrated": datetime.date.today().isoformat(),
                "notes": "No scale compensation applied"
            },
            "Epson L1800": {
                "scale_x": 100.0,
                "scale_y": 100.0,
                "date_calibrated": datetime.date.today().isoformat(),
                "notes": "Epson L1800 Default Profile"
            },
            "Mimaki UJF-3042": {
                "scale_x": 100.0,
                "scale_y": 100.0,
                "date_calibrated": datetime.date.today().isoformat(),
                "notes": "Mimaki UV Flatbed Default Profile"
            },
            "Roland LEF2": {
                "scale_x": 100.0,
                "scale_y": 100.0,
                "date_calibrated": datetime.date.today().isoformat(),
                "notes": "Roland LEF2 Desktop UV Default Profile"
            },
            "Canon TS8370": {
                "scale_x": 100.0,
                "scale_y": 100.0,
                "date_calibrated": datetime.date.today().isoformat(),
                "notes": "Canon TS Inkjet Default Profile"
            },
            "Custom": {
                "scale_x": 100.0,
                "scale_y": 100.0,
                "date_calibrated": datetime.date.today().isoformat(),
                "notes": "User-defined custom scaling compensation"
            }
        }
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(default_profiles, f, indent=4)
        except Exception as e:
            print(f"Error seeding default profiles: {e}")
        return default_profiles

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading printer profiles: {e}")
        return {}

def save_printer_profiles(profiles: Dict[str, dict]):
    filepath = get_profiles_file_path()
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(profiles, f, indent=4)
    except Exception as e:
        print(f"Error saving printer profiles: {e}")


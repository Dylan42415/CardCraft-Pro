import os
import numpy as np
import tifffile
from PIL import Image, ImageOps
from typing import List, Dict, Tuple, Any, Optional

class TIFFChannelInfo:
    def __init__(self, index: int, page_index: int, channel_in_page: int, name: str, shape: Tuple[int, int], dtype: Any):
        self.index = index                 # Global channel index in the file
        self.page_index = page_index       # Page index in the TIFF
        self.channel_in_page = channel_in_page # Channel index within that page
        self.name = name                   # Detected name of the channel
        self.shape = shape                 # (Height, Width)
        self.dtype = dtype                 # Data type (e.g. uint8)

def get_page_name(page: tifffile.TiffPage, default_name: str) -> str:
    """Helper to try and extract a page name/description from page tags."""
    # Try PageName tag (tag 285)
    page_name_tag = page.tags.get('PageName')
    if page_name_tag is not None:
        val = page_name_tag.value
        if isinstance(val, bytes):
            return val.decode('utf-8', errors='ignore').strip()
        elif isinstance(val, str):
            return val.strip()

    # Try ImageDescription tag (tag 270)
    desc_tag = page.tags.get('ImageDescription')
    if desc_tag is not None:
        val = desc_tag.value
        if isinstance(val, bytes):
            val_str = val.decode('utf-8', errors='ignore').strip()
        elif isinstance(val, str):
            val_str = val.strip()
        else:
            val_str = ""
        # Keep it short if it's a real name and ignore JSON metadata (e.g. {"shape": ...})
        if val_str and not val_str.startswith("{") and len(val_str) < 50 and "\n" not in val_str:
            return val_str

    return default_name

def get_tiff_ppi(filepath: str) -> float:
    """Attempts to read the PPI from the TIFF file tags; falls back to 300.0."""
    if not filepath:
        return 300.0
    if filepath.lower().endswith(('.psd', '.psb')):
        return 300.0
    try:
        with tifffile.TiffFile(filepath) as tif:
            page = tif.pages[0]
            resolution = page.tags.get('XResolution')
            if resolution is not None:
                val = resolution.value
                # val is typically a fraction (num, den)
                if isinstance(val, tuple) and len(val) == 2 and val[1] != 0:
                    val = val[0] / val[1]
                
                # Check resolution unit (tag 296): 2 = inch, 3 = cm
                res_unit = page.tags.get('ResolutionUnit')
                unit = res_unit.value if res_unit is not None else 2
                
                if unit == 3: # dots per cm
                    val = val * 2.54 # convert to dots per inch
                    
                if 50.0 < val < 2400.0:
                    return float(val)
    except Exception as e:
        # Avoid printing scary logs for missing tags, just return fallback
        pass
    return 300.0

def parse_psd_channels(filepath: str) -> List[TIFFChannelInfo]:
    """Parses a Photoshop PSD file to extract layers and global channels."""
    from psd_tools import PSDImage
    psd = PSDImage.open(filepath)
    channels = []
    global_idx = 0
    h, w = psd.height, psd.width
    
    # 1. Parse Layers
    for idx, layer in enumerate(psd.descendants()):
        # Only process pixel layers (skip groups and layers without pixels)
        if not layer.is_group() and (layer.width > 0 or layer.height > 0):
            pil_img = layer.topil()
            if pil_img is None:
                continue
                
            layer_name = layer.name or f"Layer {idx}"
            
            # Detect if this layer is a spot/mask pass by name
            is_spot = any(x in layer_name.lower() for x in ("white", "gloss", "emboss", "varnish", "spot", "mask"))
            
            if pil_img.mode in ("RGB", "RGBA") and not is_spot:
                # Split RGB/RGBA layers into individual channels to align with layout mapper
                channels.append(TIFFChannelInfo(
                    index=global_idx,
                    page_index=idx,
                    channel_in_page=0,
                    name=f"{layer_name} - Red",
                    shape=(h, w),
                    dtype="uint8"
                ))
                global_idx += 1
                channels.append(TIFFChannelInfo(
                    index=global_idx,
                    page_index=idx,
                    channel_in_page=1,
                    name=f"{layer_name} - Green",
                    shape=(h, w),
                    dtype="uint8"
                ))
                global_idx += 1
                channels.append(TIFFChannelInfo(
                    index=global_idx,
                    page_index=idx,
                    channel_in_page=2,
                    name=f"{layer_name} - Blue",
                    shape=(h, w),
                    dtype="uint8"
                ))
                global_idx += 1
                if pil_img.mode == "RGBA":
                    channels.append(TIFFChannelInfo(
                        index=global_idx,
                        page_index=idx,
                        channel_in_page=3,
                        name=f"{layer_name} - Alpha",
                        shape=(h, w),
                        dtype="uint8"
                    ))
                    global_idx += 1
            else:
                # Monochromatic / single grayscale channel for spot layers
                channels.append(TIFFChannelInfo(
                    index=global_idx,
                    page_index=idx,
                    channel_in_page=99,        # Code 99 indicates single composite/alpha spot layer
                    name=layer_name,
                    shape=(h, w),
                    dtype="uint8"
                ))
                global_idx += 1

    # 2. Parse Document-level Global/Spot Channels (from Photoshop's Channels tab)
    num_doc_channels = psd._record.header.channels
    alpha_names = []
    if 1006 in psd.image_resources:
        try:
            alpha_names = psd.image_resources[1006].data
        except Exception:
            pass
            
    color_mode = psd._record.header.color_mode
    num_color_channels = 4 if color_mode.name == "CMYK" else 3
    
    for c_idx in range(num_color_channels, num_doc_channels):
        alpha_idx = c_idx - num_color_channels
        if alpha_idx < len(alpha_names):
            name = alpha_names[alpha_idx]
        else:
            name = f"Spot Channel {alpha_idx + 1}"
            
        # Skip generic background 'Transparency' if layer data covers it
        if name.lower() == 'transparency':
            continue
            
        channels.append(TIFFChannelInfo(
            index=global_idx,
            page_index=-1,                 # Page_index = -1 indicates document-level global channel
            channel_in_page=c_idx,         # Channel index in composite numpy array
            name=name,
            shape=(h, w),
            dtype="uint8"
        ))
        global_idx += 1
        
    return channels

def parse_tiff_channels(filepath: str) -> List[TIFFChannelInfo]:
    """
    Parses a layered or multi-channel TIFF to extract all channels/layers.
    Returns a list of TIFFChannelInfo containing shapes, datatypes, and names.
    Supports Photoshop PSD files transparently.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    # Check for PSD header signature
    with open(filepath, 'rb') as f:
        header = f.read(4)
    if header == b'8BPS':
        return parse_psd_channels(filepath)

    channels = []
    global_idx = 0

    with tifffile.TiffFile(filepath) as tif:
        for p_idx, page in enumerate(tif.pages):
            # Read shape and tags
            # page.asarray() reads the page data. Let's inspect its shape.
            # Avoid full read if page.shape is directly available
            p_shape = page.shape
            p_dtype = page.dtype
            
            # If shape is empty or weird, skip
            if not p_shape or len(p_shape) < 2:
                continue

            height, width = p_shape[0], p_shape[1]
            num_ch = p_shape[2] if len(p_shape) > 2 else 1

            page_name = get_page_name(page, f"Page {p_idx}")

            if num_ch == 1:
                # Monochromatic/single-channel page
                channels.append(TIFFChannelInfo(
                    index=global_idx,
                    page_index=p_idx,
                    channel_in_page=0,
                    name=page_name,
                    shape=(height, width),
                    dtype=p_dtype
                ))
                global_idx += 1
            else:
                # Multi-channel page (e.g. RGB, RGBA, or CMYK)
                # Assign default channel names based on common color modes
                channel_names = []
                if num_ch == 3:
                    channel_names = ["Red", "Green", "Blue"]
                elif num_ch == 4:
                    # Could be RGBA or CMYK
                    # Let's check photmetric interpretation if possible
                    is_cmyk = False
                    photometric = page.tags.get('PhotometricInterpretation')
                    if photometric and photometric.value == 5: # CMYK
                        is_cmyk = True
                    
                    if is_cmyk:
                        channel_names = ["Cyan", "Magenta", "Yellow", "Black"]
                    else:
                        channel_names = ["Red", "Green", "Blue", "Alpha"]
                else:
                    extra_names = []
                    tag34377 = page.tags.get(34377)
                    if tag34377:
                        try:
                            val = tag34377.value
                            if isinstance(val, bytes) and val.startswith(b'8BIM'):
                                data = val[12:]
                                idx = 0
                                while idx < len(data):
                                    slen = data[idx]
                                    if slen > 0 and idx + 1 + slen <= len(data):
                                        extra_names.append(data[idx+1:idx+1+slen].decode('latin1', errors='ignore'))
                                        idx += 1 + slen
                                    else:
                                        break
                        except Exception:
                            pass

                    channel_names = ["Red", "Green", "Blue"]
                    for i in range(3, num_ch):
                        extra_idx = i - 3
                        if extra_idx < len(extra_names):
                            channel_names.append(extra_names[extra_idx])
                        else:
                            name_fallback = "Alpha" if i == 3 else f"Channel {i}"
                            channel_names.append(name_fallback)

                # Prepend page name if it's specific
                prefix = f"{page_name} - " if "Page" not in page_name else ""

                for c_idx in range(num_ch):
                    name = f"{prefix}{channel_names[c_idx]}"
                    channels.append(TIFFChannelInfo(
                        index=global_idx,
                        page_index=p_idx,
                        channel_in_page=c_idx,
                        name=name,
                        shape=(height, width),
                        dtype=p_dtype
                    ))
                    global_idx += 1

    return channels

def load_psd_layer_array(filepath: str, ch_info: TIFFChannelInfo) -> np.ndarray:
    """Extracts a specific layer's channel data from a PSD and composites it to full canvas coordinates."""
    from psd_tools import PSDImage
    psd = PSDImage.open(filepath)
    h, w = psd.height, psd.width
    
    # 1. Handle Document-level Global Spot/Alpha Channels
    if ch_info.page_index == -1:
        try:
            arr = psd.numpy()
            ch_idx = ch_info.channel_in_page
            if ch_idx < arr.shape[2]:
                channel_data = arr[..., ch_idx]
                # Scale float32 (0.0 to 1.0) to uint8 (0 to 255) raw data exactly
                return (np.clip(channel_data, 0.0, 1.0) * 255).astype(np.uint8)
        except Exception:
            pass
        return np.zeros((h, w), dtype=np.uint8)
        
    # 2. Handle Layer-level Channels
    layers = []
    for layer in psd.descendants():
        if not layer.is_group() and (layer.width > 0 or layer.height > 0):
            layers.append(layer)
            
    if ch_info.page_index >= len(layers):
        return np.zeros((h, w), dtype=np.uint8)
        
    layer = layers[ch_info.page_index]
    out_arr = np.full((h, w), 255, dtype=np.uint8)
    
    pil_img = layer.topil()
    if pil_img is None:
        return out_arr
        
    left = max(0, layer.left)
    top = max(0, layer.top)
    right = min(w, layer.right)
    bottom = min(h, layer.bottom)
    
    if right <= left or bottom <= top:
        return out_arr
        
    layer_arr = np.array(pil_img)
    
    crop_left = max(0, -layer.left)
    crop_top = max(0, -layer.top)
    crop_right = crop_left + (right - left)
    crop_bottom = crop_top + (bottom - top)
    
    sliced_layer = layer_arr[crop_top:crop_bottom, crop_left:crop_right]
    
    if ch_info.channel_in_page == 99: # Monochromatic Spot Layer
        if pil_img.mode == "RGBA" and len(sliced_layer.shape) > 2 and sliced_layer.shape[2] == 4:
            # Use Alpha channel as the mask density (opacity representing print varnish/ink)
            sliced_channel = sliced_layer[..., 3]
        elif pil_img.mode == "RGB" and len(sliced_layer.shape) > 2:
            # Convert RGB slice to Grayscale L channel
            from PIL import Image
            sliced_pil = Image.fromarray(sliced_layer, mode="RGB").convert("L")
            sliced_channel = np.array(sliced_pil)
        else:
            sliced_channel = sliced_layer
    else:
        # Standard RGB/Alpha splits
        if len(sliced_layer.shape) > 2:
            num_ch = sliced_layer.shape[2]
            ch_idx = min(ch_info.channel_in_page, num_ch - 1)
            sliced_channel = sliced_layer[..., ch_idx]
        else:
            sliced_channel = sliced_layer
        
    # Place on output canvas array
    out_arr[top:bottom, left:right] = sliced_channel
    return out_arr

def load_channel_array(filepath: str, channel_info: TIFFChannelInfo) -> np.ndarray:
    """Loads a specific channel's data as a 2D NumPy array (normalized to 0-255 uint8)."""
    # Check for PSD header signature
    with open(filepath, 'rb') as f:
        header = f.read(4)
    if header == b'8BPS':
        return load_psd_layer_array(filepath, channel_info)

    with tifffile.TiffFile(filepath) as tif:
        page = tif.pages[channel_info.page_index]
        data = page.asarray()

        # If data is multi-channel, extract the specific channel slice
        if len(data.shape) > 2:
            data = data[..., channel_info.channel_in_page]

        # Normalize data to uint8 for previewing and standardizing
        if data.dtype == np.uint8:
            return data
        elif data.dtype == np.uint16:
            return (data // 256).astype(np.uint8)
        elif data.dtype == np.bool_:
            return (data.astype(np.uint8) * 255)
        elif np.issubdtype(data.dtype, np.floating):
            # Scale 0.0 - 1.0 to 0 - 255
            return (np.clip(data, 0.0, 1.0) * 255).astype(np.uint8)
        else:
            # Fallback scaling
            d_min, d_max = data.min(), data.max()
            if d_max > d_min:
                return ((data - d_min) / (d_max - d_min) * 255).astype(np.uint8)
            else:
                return np.zeros_like(data, dtype=np.uint8)

def render_preview_rgb(
    filepath: str,
    channels: List[TIFFChannelInfo],
    mappings: Dict[str, str],
    visible_layers: List[str],
    background_color: Tuple[int, int, int] = (255, 255, 255),
    dither_settings: Dict[str, str] = None
) -> Image.Image:
    """
    Renders an RGB composite preview of the card for GUI previewing.
    Based on channel mappings and visibility settings.
    
    Arguments:
        filepath: path to the TIFF file
        channels: parsed list of TIFFChannelInfo
        mappings: dict mapping TIFF channel name to target layer (e.g. {"Red": "Base Artwork"})
        visible_layers: list of target layers currently checked visible (e.g. ["Base Artwork", "White Ink"])
    """
    # 1. Group active mapped channels
    # Find channels mapped to "Base Artwork" (typically Red, Green, Blue, Alpha)
    art_channels = {}
    white_channel = None
    gloss_channel = None
    emboss_channel = None

    rgb_target = mappings.get("Base Artwork (RGB)", "Base Artwork")

    for ch in channels:
        name_lower = ch.name.lower()
        is_rgb_ch = "red" in name_lower or "green" in name_lower or "blue" in name_lower or "alpha" in name_lower or "transparency" in name_lower or (ch.page_index == 0 and ch.channel_in_page in (0, 1, 2, 3))
        
        if is_rgb_ch:
            target = rgb_target
        else:
            target = mappings.get(ch.name)
            
        if not target or target not in visible_layers:
            continue
        
        if target == "Base Artwork":
            # Identify R, G, B, A components
            if "red" in name_lower or (not art_channels and ch.channel_in_page == 0):
                art_channels['R'] = ch
            elif "green" in name_lower or (len(art_channels) == 1 and ch.channel_in_page == 1):
                art_channels['G'] = ch
            elif "blue" in name_lower or (len(art_channels) == 2 and ch.channel_in_page == 2):
                art_channels['B'] = ch
            elif "alpha" in name_lower or "transparency" in name_lower:
                art_channels['A'] = ch
        elif target == "White Ink":
            white_channel = ch
        elif target == "Gloss":
            gloss_channel = ch
        elif target == "Emboss":
            emboss_channel = ch

    # Get width/height of the card (use first channel shape)
    if not channels:
        return Image.new("RGB", (100, 100), background_color)
    
    h, w = channels[0].shape

    # 2. Build the base artwork layer (RGBA)
    r_arr = load_channel_array(filepath, art_channels['R']) if 'R' in art_channels else np.full((h, w), background_color[0], dtype=np.uint8)
    g_arr = load_channel_array(filepath, art_channels['G']) if 'G' in art_channels else np.full((h, w), background_color[1], dtype=np.uint8)
    b_arr = load_channel_array(filepath, art_channels['B']) if 'B' in art_channels else np.full((h, w), background_color[2], dtype=np.uint8)
    
    # Base alpha (defaults to fully opaque 255)
    a_arr = load_channel_array(filepath, art_channels['A']) if 'A' in art_channels else np.full((h, w), 255, dtype=np.uint8)

    # 3mm corner radius mask for card previews
    ppi_val = get_tiff_ppi(filepath)
    r_px = max(1, round((3.0 / 25.4) * ppi_val))
    c_mask_img = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(c_mask_img)
    draw.rounded_rectangle([0, 0, w - 1, h - 1], radius=r_px, fill=255)
    outside_corners = (np.array(c_mask_img) == 0)

    r_arr[outside_corners] = background_color[0]
    g_arr[outside_corners] = background_color[1]
    b_arr[outside_corners] = background_color[2]
    a_arr[outside_corners] = 0

    base_img = Image.fromarray(np.stack([r_arr, g_arr, b_arr, a_arr], axis=-1), mode="RGBA")

    # 3. Apply overlays (White Ink, Gloss, Emboss) as semi-transparent color washes
    preview_composite = Image.new("RGBA", (w, h), background_color + (255,))
    preview_composite.paste(base_img, (0, 0), base_img)

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    if white_channel:
        w_arr = load_channel_array(filepath, white_channel)
        w_arr[outside_corners] = 255
        if dither_settings:
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
            ppi_val = get_tiff_ppi(filepath)
            w_arr = dithering.process_white_channel(w_arr, dither_mode, ppi_val, settings)
            if dither_settings.get("dither_duplicate_emboss") == "true" and emboss_channel:
                e_arr = load_channel_array(filepath, emboss_channel)
                w_arr = dithering.compose_white_channel(w_arr, e_arr, dither_settings)
        
        w_arr[outside_corners] = 255
        # Create light cyan-blue tint for white ink: RGB=(200, 220, 255) with variable alpha
        w_tint = np.zeros((h, w, 4), dtype=np.uint8)
        w_tint[..., 0] = 200 # R
        w_tint[..., 1] = 220 # G
        w_tint[..., 2] = 255 # B
        w_tint[..., 3] = (w_arr * 0.5).astype(np.uint8) # 50% opacity max
        w_overlay = Image.fromarray(w_tint, mode="RGBA")
        overlay = Image.alpha_composite(overlay, w_overlay)

    if gloss_channel:
        g_arr = load_channel_array(filepath, gloss_channel)
        g_arr[outside_corners] = 255
        # Create vibrant yellow/gold tint for gloss/varnish: RGB=(255, 235, 150)
        g_tint = np.zeros((h, w, 4), dtype=np.uint8)
        g_tint[..., 0] = 255
        g_tint[..., 1] = 235
        g_tint[..., 2] = 150
        g_tint[..., 3] = (g_arr * 0.4).astype(np.uint8) # 40% opacity max
        g_overlay = Image.fromarray(g_tint, mode="RGBA")
        overlay = Image.alpha_composite(overlay, g_overlay)

    if emboss_channel:
        e_arr = load_channel_array(filepath, emboss_channel)
        e_arr[outside_corners] = 255
        # Create emboss/height mask (magenta/purple tint): RGB=(220, 100, 220)
        e_tint = np.zeros((h, w, 4), dtype=np.uint8)
        e_tint[..., 0] = 220
        e_tint[..., 1] = 100
        e_tint[..., 2] = 220
        e_tint[..., 3] = (e_arr * 0.4).astype(np.uint8) # 40% opacity max
        e_overlay = Image.fromarray(e_tint, mode="RGBA")
        overlay = Image.alpha_composite(overlay, e_overlay)

    final_preview = Image.alpha_composite(preview_composite, overlay)
    return final_preview.convert("RGB")

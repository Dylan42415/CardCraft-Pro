import os
from typing import Optional
import numpy as np
from PIL import Image

# Reusable Spot Channel Contract
SPOT_CHANNEL_CONTRACT = {
    "dtype": np.uint8,
    "allowed_values": {0, 255},
}

# 8x8 Bayer matrix values normalized to 0.0-1.0 range
BAYER_8X8 = np.array([
    [ 0, 48, 12, 60,  3, 51, 15, 63],
    [32, 16, 44, 28, 35, 19, 47, 31],
    [ 8, 56,  4, 52, 11, 59,  7, 55],
    [40, 24, 36, 20, 43, 27, 39, 23],
    [ 2, 50, 14, 62,  1, 49, 13, 61],
    [34, 18, 46, 30, 33, 17, 45, 29],
    [10, 58,  6, 54,  9, 57,  5, 53],
    [42, 26, 38, 22, 41, 25, 37, 21]
], dtype=np.float32) / 64.0

def process_none(w_arr: np.ndarray, ppi: float, settings: dict) -> np.ndarray:
    """Returns the original white ink mask unmodified."""
    return w_arr

def process_bayer(w_arr: np.ndarray, ppi: float, settings: dict) -> np.ndarray:
    """Vectorized Ordered Bayer dithering."""
    coverage = float(settings.get("dither_coverage", "100"))
    if coverage >= 100.0 or w_arr.size == 0:
        return w_arr
        
    h, w = w_arr.shape
    bayer_grid = np.tile(BAYER_8X8, (h // 8 + 1, w // 8 + 1))[:h, :w]
    
    # 90% coverage means 10% gaps (gap_fraction = 0.10)
    gap_fraction = 1.0 - (coverage / 100.0)
    
    # Black mask is w_arr < 255
    mask = (w_arr < 255) & (bayer_grid < gap_fraction)
    out_arr = w_arr.copy()
    out_arr[mask] = 255
    return out_arr

def process_fs(w_arr: np.ndarray, ppi: float, settings: dict) -> np.ndarray:
    """Uses Pillow's built-in Floyd-Steinberg error diffusion."""
    coverage = float(settings.get("dither_coverage", "100"))
    if coverage >= 100.0 or w_arr.size == 0:
        return w_arr
        
    h, w = w_arr.shape
    gap_fraction = 1.0 - (coverage / 100.0)
    target_val = int(255.0 * (1.0 - gap_fraction))
    
    temp_img = Image.fromarray(np.full((h, w), target_val, dtype=np.uint8), mode="L")
    dithered_1bit = temp_img.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
    dithered_arr = np.array(dithered_1bit.convert("L"))
    
    out_arr = w_arr.copy()
    # Wherever dithered_arr is 0 (gaps), write 255 (white gaps) inside the black mask
    mask = w_arr < 255
    out_arr[mask] = np.where(dithered_arr[mask] == 0, 255, 0)
    return out_arr

def process_atkinson(w_arr: np.ndarray, ppi: float, settings: dict) -> np.ndarray:
    """Atkinson error diffusion."""
    coverage = float(settings.get("dither_coverage", "100"))
    if coverage >= 100.0 or w_arr.size == 0:
        return w_arr
        
    h, w = w_arr.shape
    out_arr = w_arr.copy()
    
    gap_fraction = 1.0 - (coverage / 100.0)
    target_val = int(255.0 * gap_fraction)
    
    data = np.zeros((h, w), dtype=np.float32)
    mask = w_arr < 255
    data[mask] = target_val
    
    for y in range(h):
        for x in range(w):
            if not mask[y, x]:
                continue
            old_val = data[y, x]
            new_val = 255 if old_val > 127 else 0
            out_arr[y, x] = new_val
            err = old_val - new_val
            err_8 = err / 8.0
            
            # Atkinson distributes error to 6 neighbors
            if x + 1 < w and mask[y, x+1]:
                data[y, x+1] += err_8
            if x + 2 < w and mask[y, x+2]:
                data[y, x+2] += err_8
            if y + 1 < h:
                if x - 1 >= 0 and mask[y+1, x-1]:
                    data[y+1, x-1] += err_8
                if mask[y+1, x]:
                    data[y+1, x] += err_8
                if x + 1 < w and mask[y+1, x+1]:
                    data[y+1, x+1] += err_8
            if y + 2 < h and mask[y+2, x]:
                data[y+2, x] += err_8
                
    return out_arr

def get_am_halftone_matrix(h: int, w: int, ppi: float, settings: dict) -> np.ndarray:
    """Generates the tiled AM Halftone threshold matrix using snapped pixel-grid periodic Euclidean/Spot functions."""
    angle = float(settings.get("dither_angle", "45.0"))
    lpi = float(settings.get("dither_lpi", "45.0"))
    dot_shape = settings.get("dither_dot_shape", "Round")
    
    period = ppi / lpi
    theta = np.radians(angle)
    a = int(round(period * np.cos(theta)))
    b = int(round(period * np.sin(theta)))
    if a == 0 and b == 0:
        a = 1
        
    # Cap vectors to prevent excessively large tile sizes at low LPI or high PPI
    max_val = max(abs(a), abs(b))
    if max_val > 64:
        scale = 64.0 / max_val
        a = int(round(a * scale))
        b = int(round(b * scale))
        if a == 0 and b == 0:
            a = 1
            
    N = a**2 + b**2
    g = np.gcd(a, b)
    N_tile = N // g
    
    # Generate coordinates for the tile
    y_tile, x_tile = np.meshgrid(np.arange(N_tile), np.arange(N_tile), indexing='ij')
    
    # Map to screen grid space (u, v)
    u = (a * x_tile + b * y_tile) / N
    v = (a * y_tile - b * x_tile) / N
    
    # Periodic distance components to nearest integer node (cell center)
    du = u - np.round(u)
    dv = v - np.round(v)
    
    # Evaluate metric based on shape
    if dot_shape == "Round":
        dist = np.sqrt(du**2 + dv**2)
    elif dot_shape == "Elliptical":
        dist = np.sqrt(du**2 + 1.5 * dv**2)
    elif dot_shape == "Diamond":
        dist = np.abs(du) + np.abs(dv)
    elif dot_shape == "Square":
        dist = np.maximum(np.abs(du), np.abs(dv))
    elif dot_shape == "Line":
        dist = np.abs(du)
    else:
        dist = np.sqrt(du**2 + dv**2)
        
    # Round to 5 decimal places to eliminate float precision tie-breaking issues
    dist_rounded = np.round(dist, 5)
    
    flat = dist_rounded.flatten()
    unique_vals = np.sort(np.unique(flat))
    
    threshold_tile = np.zeros_like(dist_rounded)
    for val in unique_vals:
        count_greater = np.sum(flat > val)
        count_equal = np.sum(flat == val)
        # Average rank mapping where center is 1.0 (ink) and boundaries are 0.0 (gaps)
        rank = (count_greater + (count_equal - 1) / 2.0) / len(flat)
        threshold_tile[dist_rounded == val] = rank
        
    reps_y = int(np.ceil(h / N_tile))
    reps_x = int(np.ceil(w / N_tile))
    return np.tile(threshold_tile, (reps_y, reps_x))[:h, :w]

def process_am_halftone(w_arr: np.ndarray, ppi: float, settings: dict) -> np.ndarray:
    """Rational-tangent snapped clustered-dot AM screening."""
    coverage = float(settings.get("dither_coverage", "100"))
    if coverage >= 100.0 or w_arr.size == 0:
        return w_arr
    if coverage <= 0.0:
        out_arr = w_arr.copy()
        out_arr[w_arr < 255] = 255
        return out_arr
        
    h, w = w_arr.shape
    tiled = get_am_halftone_matrix(h, w, ppi, settings)
    
    gap_fraction = 1.0 - (coverage / 100.0)
    active_mask = w_arr < 255
    active_count = np.sum(active_mask)
    if active_count == 0:
        return w_arr
        
    threshold = np.percentile(tiled[active_mask], gap_fraction * 100.0)
    
    mask = active_mask & (tiled <= threshold)
    out_arr = w_arr.copy()
    out_arr[mask] = 255
    return out_arr

def generate_blue_noise_mask(size: int = 64) -> np.ndarray:
    """Generates a high-quality deterministic pseudo-blue noise mask using Gaussian high-pass filtering in DFT domain."""
    state = np.random.RandomState(42) # Seeded for strict determinism
    white_noise = state.rand(size, size)
    
    f = np.fft.fft2(white_noise)
    fshift = np.fft.fftshift(f)
    
    # Gaussian high-pass filter
    y, x = np.meshgrid(np.arange(size), np.arange(size), indexing='ij')
    cx, cy = size // 2, size // 2
    r2 = (x - cx)**2 + (y - cy)**2
    sigma = size / 6.0
    hp_filter = 1.0 - np.exp(-r2 / (2.0 * sigma**2))
    
    fshift_filtered = fshift * hp_filter
    f_filtered = np.fft.ifftshift(fshift_filtered)
    spatial_filtered = np.real(np.fft.ifft2(f_filtered))
    
    # Rank order values to map to uniform threshold array [0.0, 1.0]
    flat = spatial_filtered.flatten()
    ranks = np.argsort(flat)
    mask = np.zeros_like(flat, dtype=np.float32)
    mask[ranks] = np.arange(len(flat), dtype=np.float32) / len(flat)
    return mask.reshape((size, size))

def process_fm_blue_noise(w_arr: np.ndarray, ppi: float, settings: dict) -> np.ndarray:
    """FM Stochastic screening using a deterministic Blue Noise void-and-cluster threshold mask."""
    coverage = float(settings.get("dither_coverage", "100"))
    if coverage >= 100.0 or w_arr.size == 0:
        return w_arr
    if coverage <= 0.0:
        out_arr = w_arr.copy()
        out_arr[w_arr < 255] = 255
        return out_arr
        
    h, w = w_arr.shape
    blue_noise = generate_blue_noise_mask(64)
    
    reps_y = int(np.ceil(h / 64))
    reps_x = int(np.ceil(w / 64))
    tiled = np.tile(blue_noise, (reps_y, reps_x))[:h, :w]
    
    gap_fraction = 1.0 - (coverage / 100.0)
    active_mask = w_arr < 255
    active_count = np.sum(active_mask)
    if active_count == 0:
        return w_arr
        
    threshold = np.percentile(tiled[active_mask], gap_fraction * 100.0)
    mask = active_mask & (tiled <= threshold)
    out_arr = w_arr.copy()
    out_arr[mask] = 255
    return out_arr

def process_hybrid_screen(w_arr: np.ndarray, ppi: float, settings: dict) -> np.ndarray:
    """Hybrid screen combining AM clustered dots for structures with FM blue noise for boundary transitions."""
    coverage = float(settings.get("dither_coverage", "100"))
    if coverage >= 100.0 or w_arr.size == 0:
        return w_arr
    if coverage <= 0.0:
        out_arr = w_arr.copy()
        out_arr[w_arr < 255] = 255
        return out_arr
        
    h, w = w_arr.shape
    
    tiled_am = get_am_halftone_matrix(h, w, ppi, settings)
    
    blue_noise = generate_blue_noise_mask(64)
    reps_y = int(np.ceil(h / 64))
    reps_x = int(np.ceil(w / 64))
    tiled_fm = np.tile(blue_noise, (reps_y, reps_x))[:h, :w]
    
    # 60% AM screen structure, 40% FM stochastic details
    blended = 0.6 * tiled_am + 0.4 * tiled_fm
    
    gap_fraction = 1.0 - (coverage / 100.0)
    active_mask = w_arr < 255
    active_count = np.sum(active_mask)
    if active_count == 0:
        return w_arr
        
    threshold = np.percentile(blended[active_mask], gap_fraction * 100.0)
    mask = active_mask & (blended <= threshold)
    out_arr = w_arr.copy()
    out_arr[mask] = 255
    return out_arr

def generate_default_texture(size: int = 256) -> np.ndarray:
    """Generates a default cross-hatch/waffle grid texture."""
    y, x = np.meshgrid(np.arange(size), np.arange(size), indexing='ij')
    l1 = np.sin((x + y) * 2.0 * np.pi / 20.0)
    l2 = np.sin((x - y) * 2.0 * np.pi / 20.0)
    return (l1 + l2 + 2.0) / 4.0

def process_custom_texture(w_arr: np.ndarray, ppi: float, settings: dict) -> np.ndarray:
    """Processes the white mask using a tiled and rank-order normalized custom grayscale texture image."""
    coverage = float(settings.get("dither_coverage", "100"))
    if coverage >= 100.0 or w_arr.size == 0:
        return w_arr
    if coverage <= 0.0:
        out_arr = w_arr.copy()
        out_arr[w_arr < 255] = 255
        return out_arr
        
    h, w = w_arr.shape
    texture_path = settings.get("dither_texture_path", "")
    
    if texture_path and os.path.exists(texture_path):
        try:
            with Image.open(texture_path) as img:
                img_gray = img.convert("L")
                tex_arr = np.array(img_gray, dtype=np.float32)
        except Exception as e:
            print(f"Error loading custom texture: {e}")
            tex_arr = generate_default_texture(256)
    else:
        tex_arr = generate_default_texture(256)
        
    th, tw = tex_arr.shape
    reps_y = int(np.ceil(h / th))
    reps_x = int(np.ceil(w / tw))
    tiled_tex = np.tile(tex_arr, (reps_y, reps_x))[:h, :w]
    
    # Rank order the tiled texture values to ensure flat uniform probability distribution
    flat = tiled_tex.flatten()
    ranks = np.argsort(flat)
    tiled = np.zeros_like(flat, dtype=np.float32)
    tiled[ranks] = np.arange(len(flat), dtype=np.float32) / len(flat)
    tiled = tiled.reshape((h, w))
    
    gap_fraction = 1.0 - (coverage / 100.0)
    active_mask = w_arr < 255
    active_count = np.sum(active_mask)
    if active_count == 0:
        return w_arr
        
    threshold = np.percentile(tiled[active_mask], gap_fraction * 100.0)
    mask = active_mask & (tiled <= threshold)
    out_arr = w_arr.copy()
    out_arr[mask] = 255
    return out_arr

# Central processor registry
PROCESSORS = {
    "None": process_none,
    "Ordered Bayer": process_bayer,
    "Floyd–Steinberg": process_fs,
    "Atkinson": process_atkinson,
    "AM Halftone": process_am_halftone,
    "FM Blue Noise": process_fm_blue_noise,
    "Hybrid Screen": process_hybrid_screen,
    "Custom Texture": process_custom_texture,
}

def process_white_channel(w_arr: np.ndarray, mode: str, ppi: float, settings: dict) -> np.ndarray:
    """Unified entry point for prepress white ink density processing."""
    processor = PROCESSORS.get(mode, process_none)
    return processor(w_arr, ppi, settings)

def calculate_coverage(original: np.ndarray, dithered: np.ndarray) -> float:
    """Calculates final ink coverage percentage relative to the original ink mask area (black ink < 255)."""
    orig_ink = np.sum(original < 255)
    if orig_ink == 0:
        return 100.0
    dith_ink = np.sum(dithered < 255)
    return float(dith_ink) / float(orig_ink) * 100.0

def compose_white_channel(
    processed_white: np.ndarray,
    emboss_mask: Optional[np.ndarray],
    settings: dict
) -> np.ndarray:
    """
    Applies the optional post-processing composition steps.
    
    Pixel Semantics:
        0   = solid white ink (active printing area)
        255 = no white ink (background/paper/holes)
        
    This is designed as an extensible composition pipeline:
    - Stage 1: Emboss Foundation (Optional duplication of emboss mask)
    - Future Stages: Gold/Silver foundations, custom masks, etc.
    """
    w_arr = processed_white.copy()
    
    # Stage 1: Duplicate Emboss Foundation
    if settings.get("dither_duplicate_emboss") == "true" and emboss_mask is not None:
        if w_arr.shape != emboss_mask.shape:
            raise ValueError(
                f"Shape mismatch in composition: processed_white {w_arr.shape} vs emboss_mask {emboss_mask.shape}"
            )
        # 0 represents active ink, np.minimum preserves active ink from either channel
        w_arr = np.minimum(w_arr, emboss_mask)
        
    return w_arr

def validate_binary_channel(channel: np.ndarray, pass_name: str, stage_name: str) -> dict:
    """
    Pure validation function to inspect a spot channel's compliance with the Spot Channel Contract.
    
    THE BINARY SPOT CHANNEL CONTRACT:
    1. Spot channels must contain only binary values: 0 (ink) and 255 (no ink).
    2. Intermediate grayscale values (1-254) are strictly prohibited.
    3. Spot channels must be stored in 8-bit (uint8) data type.
    4. Anti-aliasing must be disabled for all transformation/composition steps.
    5. Binary enforcement is a final safety net, not part of normal processing.
    
    Returns a dictionary report:
      {
         "pass": bool,
         "pass_name": str,
         "stage_name": str,
         "shape": tuple,
         "dtype": str,
         "unique_values": list of int,
         "invalid_values": list of int,
         "black_pixels": int,
         "white_pixels": int,
         "coverage_percentage": float,
         "repaired": bool
      }
    """
    report = {
        "pass": True,
        "pass_name": pass_name,
        "stage_name": stage_name,
        "shape": channel.shape,
        "dtype": str(channel.dtype),
        "unique_values": [],
        "invalid_values": [],
        "black_pixels": 0,
        "white_pixels": 0,
        "coverage_percentage": 0.0,
        "repaired": False
    }
    
    # 1. Validate data type
    target_dtype = SPOT_CHANNEL_CONTRACT["dtype"]
    if channel.dtype != target_dtype:
        report["pass"] = False
        report["invalid_values"].append(f"Invalid Dtype: {channel.dtype} (expected {target_dtype})")
        
    # 2. Check unique and invalid values
    unique_vals = np.unique(channel)
    report["unique_values"] = unique_vals.tolist()
    
    allowed = SPOT_CHANNEL_CONTRACT["allowed_values"]
    invalid = [int(v) for v in unique_vals if v not in allowed]
    if invalid:
        report["pass"] = False
        report["invalid_values"].extend(invalid)
        
    # 3. Calculate pixels and percentages
    black_count = int(np.sum(channel == 0))
    white_count = int(np.sum(channel == 255))
    report["black_pixels"] = black_count
    report["white_pixels"] = white_count
    
    total = channel.size
    if total > 0:
        # Ink coverage is the percentage of black pixels (value == 0)
        report["coverage_percentage"] = (black_count / total) * 100.0
        
    return report

def binary_enforce_channel(channel: np.ndarray) -> np.ndarray:
    """
    Pure repair function that returns a thresholded binary safety-net version of the channel.
    Values < 128 map to 0 (ink), and values >= 128 map to 255 (no ink).
    
    If the input array is already compliant, returns it directly to avoid allocations.
    """
    if channel.dtype == SPOT_CHANNEL_CONTRACT["dtype"]:
        unique_vals = np.unique(channel)
        allowed = SPOT_CHANNEL_CONTRACT["allowed_values"]
        # If all values are allowed, return original immediately
        if np.all(np.isin(unique_vals, list(allowed))):
            return channel
            
    # Apply safety-net thresholding
    return np.where(channel >= 128, 255, 0).astype(np.uint8)



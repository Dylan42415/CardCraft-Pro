import math
from typing import List, Dict, Tuple, Any
from PIL import Image, ImageDraw
from core.models import Layout, RegistrationPattern, PaperSize, CardSize, MarginSettings, RegistrationSettings

def mm_to_px(mm: float, ppi: int) -> int:
    """Converts millimeters to pixels based on the PPI (Pixels Per Inch)."""
    return round((mm / 25.4) * ppi)

def px_to_mm(px: int, ppi: int) -> float:
    """Converts pixels to millimeters based on the PPI."""
    return (px * 25.4) / ppi

def compute_grid_fit(usable: int, card: int, bleed: int) -> int:
    """Computes how many cards fit along a single dimension."""
    if usable <= 0:
        return 0
    return max(0, math.floor((usable + bleed) / (card + bleed)))

def select_best_margins(
    page_w: int, page_h: int,
    card_w: int, card_h: int,
    bleed: int, inset: int,
    corner_len: int,
    margins: MarginSettings,
    ppi: int
) -> Tuple[int, int, int, int, int, int]:
    """
    Finds the optimal grid layout and margins.
    Ensures that cards and bleed do not overlap the corner registration exclusion zones.
    
    Returns:
        (cols, rows, margin_x, margin_y, usable_width, usable_height)
    """
    # Exclude corner registration mark zones
    # If the layout is inside the registration mark's length + safety padding, it overlaps.
    # SCM corner exclusion logic:
    # A layout overlaps a corner zone if the grid bounds are closer to the page corner than (inset + corner_len) on both axes.
    
    # Minimal margins to clear registration marks
    min_margin_x = mm_to_px(margins.left_mm, ppi)
    min_margin_y = mm_to_px(margins.top_mm, ppi)
    
    # Try strategies
    # 1. Minimally sized margins
    # 2. Margins pushed inward horizontally to clear corners
    # 3. Margins pushed inward vertically to clear corners
    strategies = [
        (min_margin_x, min_margin_y),
        (min_margin_x + corner_len, min_margin_y),
        (min_margin_x, min_margin_y + corner_len),
    ]

    best = None
    best_count = 0

    def check_valid_fit(cols, rows, margin_x, margin_y, usable_w, usable_h):
        nonlocal best, best_count
        if cols <= 0 or rows <= 0:
            return
        grid_w = cols * card_w + (cols - 1) * bleed
        grid_h = rows * card_h + (rows - 1) * bleed
        
        # Calculate spacing around grid
        gap_x = margin_x + (usable_w - grid_w) / 2 - inset
        gap_y = margin_y + (usable_h - grid_h) / 2 - inset
        
        # Corner rule: if both gaps are smaller than corner length, we overlap the corner zone.
        if gap_x < corner_len and gap_y < corner_len:
            return
        
        count = cols * rows
        if count > best_count:
            best_count = count
            best = (cols, rows, margin_x, margin_y, usable_w, usable_h)

    for mx, my in strategies:
        usable_w = page_w - 2 * mx
        usable_h = page_h - 2 * my
        
        max_cols = compute_grid_fit(usable_w, card_w, bleed)
        max_rows = compute_grid_fit(usable_h, card_h, bleed)

        if max_cols == 0 or max_rows == 0:
            continue

        # Fit all
        check_valid_fit(max_cols, max_rows, mx, my, usable_w, usable_h)

        # Shrink X to clear corner
        cols_clear = max(0, math.floor((usable_w - bleed - 2 * (corner_len - mx + inset)) / (card_w + bleed)))
        check_valid_fit(cols_clear, max_rows, mx, my, usable_w, usable_h)

        # Shrink Y to clear corner
        rows_clear = max(0, math.floor((usable_h - bleed - 2 * (corner_len - my + inset)) / (card_h + bleed)))
        check_valid_fit(max_cols, rows_clear, mx, my, usable_w, usable_h)

    if best is None:
        # Fallback to simple grid without exclusion zone validation
        usable_w = page_w - 2 * min_margin_x
        usable_h = page_h - 2 * min_margin_y
        max_cols = max(1, compute_grid_fit(usable_w, card_w, bleed))
        max_rows = max(1, compute_grid_fit(usable_h, card_h, bleed))
        best = (max_cols, max_rows, min_margin_x, min_margin_y, usable_w, usable_h)

    return best

def calculate_layout_positions(
    layout: Layout, 
    ppi: int, 
    compensation_x: float = 1.0, 
    compensation_y: float = 1.0
) -> Dict[str, Any]:
    """
    Computes all pixel-based page, grid, and slot coordinates with scale compensation.
    """
    # 1. Page and card size in pixels
    page_w = mm_to_px(layout.paper_size.width_mm, ppi)
    page_h = mm_to_px(layout.paper_size.height_mm, ppi)
    card_w = mm_to_px(layout.card_size.width_mm * compensation_x, ppi)
    card_h = mm_to_px(layout.card_size.height_mm * compensation_y, ppi)
    bleed = mm_to_px(layout.card_spacing_mm, ppi)
    inset = mm_to_px(layout.registration.inset_mm, ppi)
    corner_len = mm_to_px(layout.registration.length_mm, ppi)

    # 2. Select best margins and grid fit
    cols, rows, mx, my, usable_w, usable_h = select_best_margins(
        page_w, page_h, card_w, card_h, bleed, inset, corner_len, layout.margins, ppi
    )

    # 3. Calculate grid boundaries
    grid_w = cols * card_w + (cols - 1) * bleed
    grid_h = rows * card_h + (rows - 1) * bleed

    # Centered grid start coordinates
    start_x = round(mx + (usable_w - grid_w) / 2)
    start_y = round(my + (usable_h - grid_h) / 2)

    # Slots top-left positions
    slots = []
    for r in range(rows):
        y_pos = start_y + r * (card_h + bleed)
        for c in range(cols):
            x_pos = start_x + c * (card_w + bleed)
            slots.append({
                "index": r * cols + c,
                "row": r,
                "col": c,
                "x": x_pos,
                "y": y_pos,
                "width": card_w,
                "height": card_h
            })

    return {
        "page_width": page_w,
        "page_height": page_h,
        "card_width": card_w,
        "card_height": card_h,
        "bleed": bleed,
        "cols": cols,
        "rows": rows,
        "slots": slots,
        "grid_start_x": start_x,
        "grid_start_y": start_y,
        "grid_width": grid_w,
        "grid_height": grid_h
    }

def draw_registration_marks(layout: Layout, ppi: int) -> Image.Image:
    """
    Renders the registration marks to a transparent/white PIL image of page size.
    """
    page_w = mm_to_px(layout.paper_size.width_mm, ppi)
    page_h = mm_to_px(layout.paper_size.height_mm, ppi)
    inset = mm_to_px(layout.registration.inset_mm, ppi)
    length = mm_to_px(layout.registration.length_mm, ppi)
    thickness = max(1, mm_to_px(layout.registration.thickness_mm, ppi))

    # Create transparent canvas
    img = Image.new("RGBA", (page_w, page_h), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    # Corner positions: Top-Left (TL), Top-Right (TR), Bottom-Left (BL), Bottom-Right (BR)
    # Marks are placed 'inset' pixels away from the edges
    tl = (inset, inset)
    tr = (page_w - inset, inset)
    bl = (inset, page_h - inset)
    br = (page_w - inset, page_h - inset)

    # Draw L-shaped marks helper
    def draw_l_mark(corner: Tuple[int, int], dir_x: int, dir_y: int):
        cx, cy = corner
        # Horizontal arm
        hx_start = cx
        hx_end = cx + dir_x * length
        # Vertical arm
        vy_start = cy
        vy_end = cy + dir_y * length

        # Draw arms (using black color)
        draw.line([(hx_start, cy), (hx_end, cy)], fill=(0, 0, 0, 255), width=thickness)
        draw.line([(cx, vy_start), (cx, vy_end)], fill=(0, 0, 0, 255), width=thickness)

    # Drawing based on pattern type
    if layout.registration.pattern == RegistrationPattern.THREE:
        # THREE-Mark Pattern:
        # TL: 5x5mm filled black square
        # TR: L-shape pointing bottom-left (inward)
        # BL: L-shape pointing top-right (inward)
        
        # 1. Top-Left Square Mark (5mm x 5mm)
        sq_size = mm_to_px(5.0, ppi)
        sq_half = sq_size // 2
        # Center of square is at 'tl' (inset, inset)
        sq_box = [tl[0] - sq_half, tl[1] - sq_half, tl[0] + sq_half, tl[1] + sq_half]
        draw.rectangle(sq_box, fill=(0, 0, 0, 255), outline=(0, 0, 0, 255), width=thickness)

        # 2. Top-Right L-mark: arms go Left (inward) and Down (inward)
        draw_l_mark(tr, dir_x=-1, dir_y=1)

        # 3. Bottom-Left L-mark: arms go Right (inward) and Up (inward)
        draw_l_mark(bl, dir_x=1, dir_y=-1)

    else:
        # FOUR-Mark Pattern: L-shapes at all four corners pointing inward
        # TL: arms go Right and Down
        draw_l_mark(tl, dir_x=1, dir_y=1)
        # TR: arms go Left and Down
        draw_l_mark(tr, dir_x=-1, dir_y=1)
        # BL: arms go Right and Up
        draw_l_mark(bl, dir_x=1, dir_y=-1)
        # BR: arms go Left and Up
        draw_l_mark(br, dir_x=-1, dir_y=-1)

    return img

def get_default_layouts() -> List[Layout]:
    """Returns standard, predefined card print layouts matching SCM specifications."""
    return [
        Layout(
            id="a4_8_cards_standard",
            name="A4 8 Cards (Standard)",
            paper_size=PaperSize(width_mm=297.0, height_mm=210.0), # Landscape
            card_size=CardSize(width_mm=63.0, height_mm=88.0, radius_mm=3.0),
            rows=2,
            columns=4,
            card_spacing_mm=1.25,
            bleed_mm=1.5,
            margins=MarginSettings(top_mm=10.0, bottom_mm=10.0, left_mm=10.0, right_mm=10.0),
            registration=RegistrationSettings(
                pattern=RegistrationPattern.THREE,
                inset_mm=10.0,
                length_mm=9.4,
                thickness_mm=1.0
            )
        ),
        Layout(
            id="a4_9_cards_borderless",
            name="A4 9 Cards (Borderless)",
            paper_size=PaperSize(width_mm=210.0, height_mm=297.0), # Portrait
            card_size=CardSize(width_mm=63.0, height_mm=88.0, radius_mm=3.0),
            rows=3,
            columns=3,
            card_spacing_mm=1.25,
            bleed_mm=1.5,
            margins=MarginSettings(top_mm=3.5, bottom_mm=3.5, left_mm=3.5, right_mm=3.5),
            registration=RegistrationSettings(
                pattern=RegistrationPattern.THREE,
                inset_mm=3.5,
                length_mm=5.0,
                thickness_mm=1.0
            )
        ),
        Layout(
            id="letter_8_cards_standard",
            name="Letter 8 Cards (Standard)",
            paper_size=PaperSize(width_mm=279.4, height_mm=215.9), # Landscape
            card_size=CardSize(width_mm=63.5, height_mm=88.9, radius_mm=3.0),
            rows=2,
            columns=4,
            card_spacing_mm=1.25,
            bleed_mm=1.5,
            margins=MarginSettings(top_mm=10.0, bottom_mm=10.0, left_mm=10.0, right_mm=10.0),
            registration=RegistrationSettings(
                pattern=RegistrationPattern.THREE,
                inset_mm=10.0,
                length_mm=8.04,
                thickness_mm=1.0
            )
        ),
        Layout(
            id="letter_9_cards_borderless",
            name="Letter 9 Cards (Borderless)",
            paper_size=PaperSize(width_mm=215.9, height_mm=279.4), # Portrait
            card_size=CardSize(width_mm=63.5, height_mm=88.9, radius_mm=3.0),
            rows=3,
            columns=3,
            card_spacing_mm=1.25,
            bleed_mm=1.5,
            margins=MarginSettings(top_mm=3.5, bottom_mm=3.5, left_mm=3.5, right_mm=3.5),
            registration=RegistrationSettings(
                pattern=RegistrationPattern.THREE,
                inset_mm=3.5,
                length_mm=5.0,
                thickness_mm=1.0
            )
        )
    ]

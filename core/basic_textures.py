import os
import subprocess
import numpy as np
from PIL import Image, ImageDraw

INKSCAPE_PATH = r"C:\Program Files\Inkscape\bin\inkscape.com"
TEXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "textures")
os.makedirs(TEXTURES_DIR, exist_ok=True)


def generate_svg_crosshatch(width_mm: float = 63.0, height_mm: float = 88.0, radius_mm: float = 3.0, spacing_mm: float = 0.5) -> str:
    """Generates diagonal crosshatch grid SVG texture overlay."""
    sp = spacing_mm
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width_mm}mm" height="{height_mm}mm" viewBox="0 0 {width_mm} {height_mm}">
  <defs>
    <pattern id="crosshatch" width="{sp}" height="{sp}" patternUnits="userSpaceOnUse">
      <path d="M 0 {sp} L {sp} 0 M 0 0 L {sp} {sp}" fill="none" stroke="#000000" stroke-width="0.08"/>
    </pattern>
  </defs>
  <rect width="{width_mm}" height="{height_mm}" fill="#ffffff"/>
  <rect width="{width_mm}" height="{height_mm}" rx="{radius_mm}" ry="{radius_mm}" fill="url(#crosshatch)"/>
</svg>'''
    return svg


def generate_svg_stipple(width_mm: float = 63.0, height_mm: float = 88.0, radius_mm: float = 3.0, spacing_mm: float = 0.4, dot_radius_mm: float = 0.1) -> str:
    """Generates dot stipple matrix SVG texture overlay."""
    sp = spacing_mm
    r = dot_radius_mm
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width_mm}mm" height="{height_mm}mm" viewBox="0 0 {width_mm} {height_mm}">
  <defs>
    <pattern id="stipple" width="{sp}" height="{sp}" patternUnits="userSpaceOnUse">
      <circle cx="{sp/2}" cy="{sp/2}" r="{r}" fill="#000000"/>
    </pattern>
  </defs>
  <rect width="{width_mm}" height="{height_mm}" fill="#ffffff"/>
  <rect width="{width_mm}" height="{height_mm}" rx="{radius_mm}" ry="{radius_mm}" fill="url(#stipple)"/>
</svg>'''
    return svg


def generate_svg_holo_lines(width_mm: float = 63.0, height_mm: float = 88.0, radius_mm: float = 3.0, spacing_mm: float = 0.25) -> str:
    """Generates parallel vertical diffraction lines SVG texture overlay."""
    sp = spacing_mm
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width_mm}mm" height="{height_mm}mm" viewBox="0 0 {width_mm} {height_mm}">
  <defs>
    <pattern id="lines" width="{sp}" height="{height_mm}" patternUnits="userSpaceOnUse">
      <line x1="0" y1="0" x2="0" y2="{height_mm}" stroke="#000000" stroke-width="0.08"/>
    </pattern>
  </defs>
  <rect width="{width_mm}" height="{height_mm}" fill="#ffffff"/>
  <rect width="{width_mm}" height="{height_mm}" rx="{radius_mm}" ry="{radius_mm}" fill="url(#lines)"/>
</svg>'''
    return svg


def generate_svg_diamond_grid(width_mm: float = 63.0, height_mm: float = 88.0, radius_mm: float = 3.0, size_mm: float = 0.8) -> str:
    """Generates diamond foil grid SVG texture overlay."""
    s = size_mm
    half = s / 2
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width_mm}mm" height="{height_mm}mm" viewBox="0 0 {width_mm} {height_mm}">
  <defs>
    <pattern id="diamond" width="{s}" height="{s}" patternUnits="userSpaceOnUse">
      <path d="M {half} 0 L {s} {half} L {half} {s} L 0 {half} Z" fill="none" stroke="#000000" stroke-width="0.08"/>
    </pattern>
  </defs>
  <rect width="{width_mm}" height="{height_mm}" fill="#ffffff"/>
  <rect width="{width_mm}" height="{height_mm}" rx="{radius_mm}" ry="{radius_mm}" fill="url(#diamond)"/>
</svg>'''
    return svg


BASIC_TEXTURE_GENERATORS = {
    "Crosshatch Grid": generate_svg_crosshatch,
    "Dot Stipple": generate_svg_stipple,
    "Holographic Lines": generate_svg_holo_lines,
    "Diamond Foil Grid": generate_svg_diamond_grid,
}


def build_basic_texture_files(ppi: int = 600) -> dict:
    """
    Generates SVG vector files for all basic texture presets.
    Returns dictionary mapping preset names to compiled SVG file paths.
    """
    compiled_paths = {}
    for name, gen_func in BASIC_TEXTURE_GENERATORS.items():
        slug = name.lower().replace(" ", "_")
        svg_filename = f"preset_{slug}.svg"
        svg_path = os.path.join(TEXTURES_DIR, svg_filename)
        
        svg_data = gen_func(width_mm=63.0, height_mm=88.0, radius_mm=3.0)
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(svg_data)
            
        compiled_paths[name] = svg_path
            
    return compiled_paths

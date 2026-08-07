# Wiki 04: Advanced Masking — Blend If, Apply Image & Calculations

Beyond basic layer masks, Photoshop provides advanced non-destructive mathematical tools for extracting complex textures, glows, and height maps.

---

## 1. Blend If (Non-Destructive Luminance Masking)

**Blend If** hides pixels based on brightness values without manual brush painting or selection outlines.

### How to Access:
1. Double-click any layer in the **Layers Panel** to open **Layer Style**.
2. At the bottom of the dialog, locate **Blend If: Gray**.

### Key Mechanics:
- **This Layer Sliders**:
  - Dragging the **Black slider to the right**: Hides dark pixels on the current layer.
  - Dragging the **White slider to the left**: Hides light pixels on the current layer.
- **Alt + Click / Drag (Split Slider)**:
  - Splitting the slider creates smooth, anti-aliased luminosity transitions.

### TCG Use Cases:
- **Extracting Gold Highlights**: Hide dark shadows without painting masks.
- **Isolating Energy Glows**: Set layer to Screen/Color Dodge and adjust Blend If to drop out dark background pixels automatically.

---

## 2. Apply Image & Calculations

**Apply Image** and **Calculations** combine channels mathematically to produce precise grayscale masks.

### Apply Image (`Image → Apply Image`):
- Blends one layer/channel directly into another layer mask.
- Used to copy high-contrast luminosity data into a spot channel or layer mask.

### Calculations (`Image → Calculations`):
- Takes two channels (e.g. Red channel from Layer A and Blue channel from Layer B), applies a blend mode (e.g. Multiply, Overlay, Difference), and outputs a **New Alpha Channel**.
- Used by prepress professionals to build **Emboss Height Maps** and **Tactile Texture Spot Masks**.

---

## 3. Blend Modes & Masking Synergy

| Blend Mode | Category | Use with Masking For |
|---|---|---|
| **Multiply** | Darken | Shadows, dirty textures, card frame darkening |
| **Screen / Linear Dodge** | Lighten | Energy blasts, aura glows, foil shine overlays |
| **Overlay / Soft Light** | Contrast | Tactile textures, metallic sheen enhancements |
| **Color Dodge** | Special Glow | Intense laser/fire highlights on character art |

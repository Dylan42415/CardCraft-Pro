# Wiki 01: Masking Fundamentals for TCG Card Production

Masking is the single most important skill in digital TCG card production (proxies, custom cards, alternate art, and UV prepress). 

Professional card workflows rely almost exclusively on **non-destructive masking** rather than pixel erasure. Non-destructive editing preserves original image pixels, allows instant recovery, enables feathering and refinement, and ensures clean spot channel generation for specialty printing.

---

## 1. The 5 Masking Systems in Photoshop

| Mask Type | Primary Purpose | Destructive? | TCG Importance |
|---|---|---|---|
| **Layer Mask** | Non-destructively hides or reveals areas of a pixel layer using grayscale values | **No** | ⭐⭐⭐⭐⭐ (Essential) |
| **Clipping Mask** | Restricts the visibility of a layer to the shape/alpha of the layer below it | **No** | ⭐⭐⭐⭐⭐ (Essential) |
| **Channel Mask** | Alpha channels created from color channels or custom selections | **No** | ⭐⭐⭐⭐ (Prepress & Spot Ink) |
| **Vector Mask** | Uses mathematical resolution-independent pen paths to mask sharp edges | **No** | ⭐⭐⭐ (Frames & Borders) |
| **Quick Mask** | Temporary painting mode (`Q`) for quick custom selection generation | **No** | ⭐⭐⭐ (Selection Refinement) |

---

## 2. Layer Mask Mechanics

A Layer Mask controls opacity on a per-pixel basis using a greyscale map:

- **Pure White (`RGB 255, 255, 255`)** = 100% Opaque (Fully Visible)
- **Pure Black (`RGB 0, 0, 0`)** = 0% Opaque (Fully Hidden / Transparent)
- **Grayscale / Intermediate Gray (`RGB 128, 128, 128`)** = Partial Transparency

### Destructive Erasing vs. Non-Destructive Layer Masking

```
[ BAD - Destructive ]
Import Art → Use Eraser Tool → Pixels Destroyed Forever

[ GOOD - Non-Destructive ]
Import Art → Create Layer Mask → Paint Black/White → Fully Editable & Recoverable
```

---

## 3. Essential Mask Brush Settings for Cards

When painting directly on a Layer Mask thumbnail:

- **Key Shortcut**: Press **`X`** to quickly swap Foreground and Background colors (Black $\leftrightarrow$ White).
- **Brush Hardness**:
  - **Hard Brush (85%–100%)**: Used for sharp edges like armor, swords, card frames, text boxes, and anime outlines.
  - **Soft Brush (0%–20%)**: Used for soft elements like magical glows, smoke, fog, ambient lighting, and shadows.
- **Brush Opacity vs. Flow**:
  - For solid mask painting: 100% Opacity, 100% Flow.
  - For subtle lighting/glow transitions: 100% Opacity, 10%–20% Flow (acts like an airbrush).
- **Feather & Density**:
  - **Feather**: Softens the mask boundary. For TCG cards, keep feather very sharp (**0.0 px to 0.5 px**). Never use large feather values on card subject cutouts.
  - **Density**: Controls the maximum visibility of masked areas (similar to reducing mask opacity).

---

## 4. Select and Mask Workspace (Edge Refinement)

The **Select and Mask** workspace is used to refine hair, fur, cloth, and complex subject edges:

1. **Detection Radius**: Higher for soft hair/fur; **lower/0** for clean anime character lines.
2. **Smooth**: Rounds jagged edges (0–2 for anime art; 5–15 for realistic photos).
3. **Contrast**: Sharpens mask edges after feathering.
4. **Shift Edge**: Moves mask boundaries inward (e.g. **-5%** shift eliminates white background halos on dark hair).
5. **Output**: Always select **Output to: Layer Mask**.

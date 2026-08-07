# Wiki 05: Standardized 12-Layer TCG Card PSD Structure

To maintain consistency across large proxy sets and multi-pass UV print runs, every card template should follow a standardized 12-layer PSD structure.

---

## 1. The Standardized 12-Layer Stack

```
📁 Card_Template.psd
│
├── 12 [SPOT] Emboss Mask (Spot Channel / Layer Mask)
├── 11 [SPOT] Foil Mask (Spot Channel / Layer Mask)
├── 10 [SPOT] Varnish / Gloss Mask (Spot Channel / Layer Mask)
├── 09 [SPOT] White Ink Mask (Spot Channel / Layer Mask)
│
├── 08 Adjustment Layers (Curves, Color Balance, Vibrance)
├── 07 Texture Overlays (Clipping Masks for Foil / Noise)
├── 06 Typography & Frame (Card Name, HP, Attack, Text Box, Rarity Logo)
├── 05 Highlights & Energy Glows (Blend Modes: Screen / Color Dodge)
├── 04 Shadows & Ambient Occlusion (Blend Mode: Multiply)
├── 03 Special Effects & Aura (Magical particles, fire, lightning)
├── 02 Character Subject (Clean cutout + Attached Layer Mask)
└── 01 Background Artwork (Full bleed artwork base)
```

---

## 2. Advantages of the Standard 12-Layer Structure

1. **Non-Destructive Workflows**: Every element can be tweaked, recolored, or hidden without affecting adjacent artwork layers.
2. **Automated Batch Processing**: Standardized layer naming allows Python and MCP scripts to find and update card text, swap character artwork, or generate spot channels automatically across hundreds of cards.
3. **Prepress Reliability**: Spot channel masks (09–12) map directly to UV printer channels, preventing misaligned print passes.

---

## 3. Card Dimensions & Layout Specifications

| Property | Official Spec | Prepress Canvas Spec |
|---|---|---|
| **Card Physical Size** | 63.0 mm × 88.0 mm (Poker / One Piece / MTG / Pokémon) | 63.0 mm × 88.0 mm |
| **Bleed Margin** | 1.5 mm on all sides | 66.0 mm × 91.0 mm (with bleed) |
| **Corner Radius** | 3.0 mm rounded cut | 3.0 mm rounded cut |
| **Target Print Resolution** | 600 PPI | 600 PPI ($1488 \times 2079\text{ px}$ canvas) |
| **A4 Sheet Grid** | 3 columns × 3 rows (9 cards per A4 page) | Centered grid with 3.5 mm margins |

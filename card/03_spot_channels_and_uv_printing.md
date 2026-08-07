# Wiki 03: Spot Channels & Specialty UV Printing Workflow

Specialty trading card printing (UV flatbed printers like Roland VersaUV or Mimaki UJF) requires **Spot Channels** to drive non-CMYK specialty print heads:
- **White Ink Pass**: Base undercoat printed on transparent/holographic stock.
- **Gloss UV / Varnish Pass**: Clear shiny tactile varnish applied over specific highlights or full card.
- **Emboss Pass**: Raised 3D texture maps.
- **Foil Stamping Pass**: Metallic gold, silver, or rainbow holographic foil placement.

---

## 1. Spot Channel Architecture

Unlike standard RGB or CMYK channels (which combine to render full-color artwork), a **Spot Channel** operates as an independent grayscale ink mask:

- **Active Ink (`0` / Pure Black)** = 100% Ink Coverage on Press.
- **No Ink (`255` / Pure White)** = 0% Ink Coverage.

> [!IMPORTANT]
> For UV spot inks (White, Varnish, Emboss), spot channels MUST adhere to the strict **Binary Contract `{0, 255}`**. Any anti-aliased gray pixels will cause partial ink curing, smearing, or bleeding on press.

---

## 2. Step-by-Step Spot Channel Workflows

### A. White Ink Mask Workflow (Undercoat)
1. Complete character and card layout.
2. Select the character subject (`Select → Select Subject`).
3. Expand selection by **1 pixel** (`Select → Modify → Expand → 1px`) to prevent white ink border bleed.
4. Open **Channels Panel** (`Window → Channels`).
5. Click Panel Menu $\rightarrow$ **New Spot Channel**.
6. Set Name: `White`, Solidity: `100%`.
7. Fill selection with **Pure Black (`0`)**.

### B. Varnish / Gloss UV Workflow
1. Isolate artwork areas intended for shiny finish (e.g. eyes, attack numbers, logos, character highlights).
2. Create active selection using **Color Range** or **Layer Mask**.
3. Create **New Spot Channel** named `Varnish` or `Gloss`.
4. Fill selection with **Pure Black (`0`)**.

### C. Gold Foil & Emboss Workflows
1. Select gold border ornaments, foil accents, or card text.
2. Create **New Spot Channel** named `Foil` or `Emboss`.
3. Fill selection with **Pure Black (`0`)**.

---

## 3. Prepress TIFF Export Contract

When exporting the final card file for printing:
- Export format: **Multi-channel Layered TIFF**.
- Resolution: **600 PPI** (Professional high-fidelity print resolution).
- Color Mode: CMYK + Spot Channels.
- Embedded Metadata: Include printer scale compensation and PPI tags.

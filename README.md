# 🎴 CardCraft Pro

**CardCraft Pro** is a high-precision Trading Card Game (TCG) prepress and spot-channel generation suite designed for professional TCG card creation, spot varnish/embossing, white ink dithering, preset vector texture overlays, and sheet layout printing.

---

## 🌟 Key Features

* **TCG Card Standards Compliance**: Built strictly around standard TCG specifications ($63 \times 88\text{ mm}$ with $3.0\text{ mm}$ corner radius, 600 PPI resolution).
* **Multi-Channel Spot Ink Support**:
  * **White Ink Channel (`1` / Ctrl+6)**: Full white underprint layer with RIP halftone dithering.
  * **Embossing Channel (`3` / Ctrl+7)**: Binary spot embossing masks.
  * **Spot Gloss / Foil Channels**: Dedicated spot layers mapped to Photoshop Resource Block Tag 34377 extra samples.
* **Vector SVG Texture Library**:
  * Japanese *Seigaiha* (青海波) wave scale patterns.
  * Manga speedlines & multi-directional curved hatching.
  * Cracked Ice / Shattered Prismatic foil.
  * Cosmic Starburst & Holographic Hexagon grid matrix.
* **Sheet Layout & Cutting Templates**:
  * 9-Card A4 sheet layout manager.
  * Silhouette / Cricut cutting line export (`.dxf` and `.svg`).
* **Photoshop PSD & Multi-Layer TIFF Export**: Seamless interop with Adobe Photoshop and professional printing presses.

---

## 📐 Card Specifications

| Specification | Value |
|---|---|
| **Width** | $63.0\text{ mm}$ |
| **Height** | $88.0\text{ mm}$ |
| **Corner Radius** | $3.0\text{ mm}$ (`rx="3.0" ry="3.0"`) |
| **Default Resolution** | $600\text{ PPI}$ ($1488 \times 2079\text{ px}$) |
| **Color Space** | RGBA / Multi-channel Spot CMYK |

---

## 🚀 Quick Start

### 1. Installation

Ensure Python 3.10+ is installed on your system.

```bash
git clone https://github.com/your-username/CardCraft-Pro.git
cd CardCraft-Pro
pip install -r requirements.txt
```

### 2. Launch Desktop Application

```bash
python app.py
```

---

## 📁 Repository Structure

```text
CardCraft-Pro/
├── core/                   # Core dithering, export engine & texture generators
│   ├── basic_textures.py   # SVG vector texture library
│   ├── dithering.py        # Halftone RIP & spot channel dithering
│   └── export_engine.py    # Multi-channel TIFF/PSD & sheet layout exporter
├── gui/                    # PySide6 desktop user interface
│   └── mapping_panel.py    # Texture & spot channel mapping controls
├── textures/               # Compiled vector SVG texture overlays
├── requirements.txt        # Python dependency manifest
├── app.py                  # Application entry point
└── README.md               # Project documentation
```

---

## 📜 License

MIT License. See `LICENSE` for details.

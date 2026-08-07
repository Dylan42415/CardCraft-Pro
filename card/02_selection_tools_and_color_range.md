# Wiki 02: Selection Tools & Color Range Extraction

Precise selections are the foundation of clean layer masks and spot channels. Photoshop provides multiple tools for selecting subjects, backgrounds, and specific color tones.

---

## 1. Selection Tool Comparison for TCG Production

| Tool | AI Powered? | Best Use Case for Cards | Precision |
|---|---|---|---|
| **Object Selection Tool** | Yes (Adobe Sensei) | Instant character subject isolation | High |
| **Select Subject** | Yes (Adobe Sensei) | One-click primary character selection | High |
| **Color Range** | No | Extracting gold foil, glows, highlights, and specific color channels | Extreme |
| **Pen Tool** | No (Vector paths) | Sharp card frames, borders, emblems, and logos | Absolute (Pixel Perfect) |
| **Quick Selection Tool** | Semi-automatic | Selecting background regions or large uniform areas | Medium |
| **Magic Wand** | No (Tolerance based) | Solid flat backgrounds or single-color blocks | Medium |
| **Quick Mask Mode (`Q`)** | Manual | Hand-painting complex selections with brush tools | High |

---

## 2. Extracting Foil & Glows with Color Range

**Color Range** (`Select → Color Range`) is the primary tool for isolating metallic foils, gold ornaments, and energy glows from card artwork.

### Color Range Workflow for Gold Foil Extraction:
1. Go to **Select → Color Range**.
2. Set Selection Preview to **Quick Mask** or **Grayscale**.
3. Use the Eyedropper tool to click on the gold ornament/highlight.
4. Adjust **Fuzziness** (typically 20 to 50):
   - **Low Fuzziness**: Strict color matching.
   - **High Fuzziness**: Includes adjacent golden tones and gradients.
5. Click **OK** to generate the selection.
6. Convert selection to a **Layer Mask** or **Spot Channel**.

---

## 3. Pen Tool (Vector Cutouts)

For sharp card frames, copyright text blocks, attack/cost circles, and rectangular borders, standard pixel brushes can leave blurry edges.

### Pen Tool Workflow:
1. Select **Pen Tool (`P`)** in **Path Mode**.
2. Draw precise vector anchor points around the border or logo.
3. Right-click path $\rightarrow$ **Make Selection** (Feather radius: `0.0 px`).
4. Apply selection directly to a **Layer Mask** or **Vector Mask**.

---

## 4. Quick Mask Mode (`Q`)

Pressing **`Q`** toggles **Quick Mask Mode**:
- Selected areas remain normal color.
- Unselected / protected areas are covered with a translucent **red overlay**.
- Paint with a black/white brush to fine-tune complex character selections.
- Press **`Q`** again to convert the painted overlay back into an active selection march.

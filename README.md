# VG Painter Utilities

**VG Painter Utilities** is a suite of productivity tools for **Adobe Substance 3D Painter**, adding layer shortcuts, baking helpers, a full Collection system, and more — all accessible from a dedicated **VG Utilities** menu.

> Compatible with Substance 3D Painter 9.x and later (PySide6).

---

## ☕ Support My Work

If you find this project useful and want to show your appreciation, a small donation is always welcome — it helps me keep building and improving!

[![Donate with PayPal](https://www.paypalobjects.com/en_US/i/btn/btn_donate_LG.gif)](https://www.paypal.me/cgvinny)

Thank you! 🙏

---

## Installation

1. Download the latest release from the [Releases page](https://github.com/cgvinny/vg_painter_utilities/releases).
2. Copy the `plugins/` and `modules/` folders into your Painter Python directory:

   ```
   C:\Users\[USER]\Documents\Adobe\Adobe Substance 3D Painter\python\
   ```

   If prompted that the folder already exists, confirm — it will only add or update files.

3. In Substance 3D Painter, go to **Python → Reload All Plugins**.
4. A **VG Utilities** menu will appear in the top menu bar.

> **Video walkthrough:** [https://youtu.be/KjRgUkQnXDk](https://youtu.be/KjRgUkQnXDk)

---

## Features

### Layer Operations

| Action | Default Shortcut |
|---|---|
| New Paint Layer | `Ctrl + P` |
| New Fill Layer — Base Color only | `Ctrl + F` |
| New Fill Layer — Height only | `Ctrl + Alt + F` |
| New Fill Layer — all channels | `Ctrl + Shift + F` |
| New Fill Layer — no channels | `Alt + F` |

---

### Mask Operations

| Action | Default Shortcut |
|---|---|
| Add Mask… (popup) | `Ctrl + Shift + M` |

The popup lets you choose the mask type:
- Black Mask / White Mask
- Mask with Fill Effect
- Mask with Paint Layer
- Mask with AO Generator
- Mask with Curvature Generator
- Mask with Levels
- Mask with Compare Mask
- Mask with Color Selection

---

### Stack Utilities

| Action | Default Shortcut |
|---|---|
| Create ID map from selected group | `Ctrl + Shift + I` |
| ID Color Swap | — |
| Create Reference Point Layer | `Ctrl + R` |

**Create Reference Point Layer** inserts a named marker layer used as a visual anchor in the stack. The default prefix is configurable in Settings.

---

### Baking

| Action | Default Shortcut |
|---|---|
| Quick Bake — current Texture Set | `Ctrl + B` |
| Bake All — all Texture Sets | `Ctrl + Shift + B` |

Both operations bake mesh maps (Normal, World Space Normal, AO, Curvature, Position, Thickness, ID) at the native resolution of each Texture Set.

---

### Collections

The Collection system lets you define sets of **material slots**, each linked to a color in an ID map. Collections are saved as Smart Materials (`.spsm`) and can be applied to any project.

#### Workflow

1. **Open the panel** — *VG Utilities → Collections…*
2. **Create a collection** — Click **+ New Collection**, enter a name and define your material slots (name + ID map color for each).
3. **Generate the structure** — The layer group structure is automatically inserted into the active Texture Set. Fill in each group with your materials.
4. **Save as Smart Material** — Click **Save as Smart Material** in the floating overlay. This saves the collection as a reusable `.spsm` file.
5. **Load into a project** — Click the **▶** button on any collection row to insert it into the active Texture Set's layer stack.

#### Panel Buttons (per collection)

| Button | Action |
|---|---|
| ▶ | Insert Smart Material into the active Texture Set |
| ⚙ | Edit collection settings, regenerate structure, update Smart Material |
| ⧉ | Duplicate collection |
| ⚡ | **Batch Apply** — apply to multiple projects (see below) |
| ✕ | Delete collection |

#### Batch Apply ⚡

Applies a collection's Smart Material to **every Texture Set in every `.spp` project** found in a selected folder — fully automated.

1. Click **⚡** on the collection row.
2. Select a folder containing `.spp` files (auto-saves are automatically excluded).
3. The number of detected projects is shown. Click **Launch Batch** and confirm.
4. Painter opens each project, inserts the collection into all Texture Sets, saves, and moves to the next.
5. A live log shows the result (✓ / ✗) for each project.

**Option — Replace collection if already present:** when checked, any existing groups with the same collection name are removed before inserting — even if there are duplicates from previous runs.

> The collection must have a saved Smart Material (`.spsm`) before running a batch.

---

### Base Color Manager

*VG Utilities → Base Color Manager* opens a dockable panel that scans the active Texture Set for fill layers with an active **Base Color** channel and displays their colors as an editable list.

#### Features

- **Click a color swatch** to open a color picker and apply the new color to the layer instantly.
- **Click a layer name** to select that layer in the stack.
- **Drag a color** from the Applied Colors strip at the bottom onto any row swatch to apply it directly.
- **Applied Colors strip** — records every color change made in the session. Click a swatch to apply it to the currently selected fill layer(s) in the stack.
- **Ignore hidden layers** *(checked by default)* — skips layers that are not visible.
- **Merge identical colors** — collapses rows that share the same color into a single row, so editing one updates all layers in the group simultaneously.
- **Hue only** — when changing or dropping a color, only the Hue is replaced; each layer's original Saturation and Brightness are preserved.
- **Multi-color substances** — if a Substance material exposes multiple color parameters, each parameter gets its own row (e.g. *Terrazzo — Color1*, *Terrazzo — Grout Color*).
- **Checkbox selection** — check multiple rows to apply a color change or a drag-and-drop to all of them at once. Clicking **×** on any row also removes all currently checked rows.
- **Auto-refresh** — the list automatically updates when you switch to a different Texture Set.
- **↺ button** — manually refresh the list at any time.

---

### Settings

*VG Utilities → Settings…* opens the settings dialog, where you can:
- Reassign keyboard shortcuts for all actions
- Set the default prefix for Reference Point layers

---

### About & Updates

*VG Utilities → About VG Utilities…* shows the installed version, author, and license.

A **Check for Updates** button queries the GitHub releases API. A silent background check also runs 8 seconds after Painter starts — if a newer version is available, a message is logged to the Painter console.

---

## Contact

Issues, feedback, or contributions: [cgvinny@adobe.com](mailto:cgvinny@adobe.com)  
GitHub: [https://github.com/cgvinny/vg_painter_utilities](https://github.com/cgvinny/vg_painter_utilities)

Please read the [LICENSE](LICENSE) file for usage terms.

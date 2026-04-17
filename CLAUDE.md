# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Python plugin collection for **Adobe Substance 3D Painter**. Code runs inside Painter's embedded Python interpreter — it cannot be executed standalone. The `substance_painter` package (e.g., `substance_painter.layerstack`, `substance_painter.textureset`, `substance_painter.baking`) is only available at Painter runtime.

## Directory Structure

- `plugins/` — Entry point plugins loaded by Painter. `vg_menu_launcher.py` registers a "VG Utilities" menu and wires menu actions to utility functions.
- `modules/vg_pt_utils/` — Reusable utility library imported by plugins.
- `startup/` — Scripts run automatically at Painter startup (currently empty).

## How Plugins Are Loaded

Painter loads scripts from `plugins/` and calls `start_plugin()` / `close_plugin()` lifecycle hooks. The plugin registers `PySide6` UI elements and must clean them up in `close_plugin()` by calling `ui.delete_ui_element()` on every widget stored in `plugin_menus_widgets`.

During development, `reload_plugin()` in `vg_menu_launcher.py` reloads all modules via `importlib.reload()` — call this from Painter's Python console after editing module files to pick up changes without restarting Painter.

## Module Architecture (`vg_pt_utils`)

| Module | Responsibility |
|---|---|
| `vg_project_info.py` | `TextureSetInfo` — fetches name, channels, UV tile coordinates from the active or specified stack |
| `vg_layerstack.py` | `LayerManager` — creates fill/paint layers, manages selection, generates ref-point layers; `MaskManager` — adds black/white masks and inserts generator effects (AO, Curvature) |
| `vg_export.py` | Export pipeline classes (`ExportConfigGenerator`, `TextureExporter`, `TextureImporter`, `LayerTextureAssigner`) plus top-level functions `create_layer_from_stack()` and `flatten_stack()` |
| `vg_baking.py` | `BakingParameterConfigurator`, `BakingProcessManager` — configures and launches async baking; `quick_bake()` bakes mesh maps [1,2,3,4,5,8,9] at the active texture set's native resolution |

## API Documentation

The full `substance_painter` Python API reference is available locally as HTML files:

**Root:** `C:/Program Files/Adobe/Adobe Substance 3D Painter/resources/python-doc/index.html`

Key module pages (under `.../python-doc/substance_painter/`):

| Page | Contenu utile |
|---|---|
| `baking.html` | `BakingParameters`, `bake_async` |
| `export.html` | `export_project_textures`, `get_default_export_path`, `ExportStatus` |
| `layerstack/edition.html` | `insert_fill/paint/generator_effect`, `InsertPosition`, `BlendingMode`, `MaskBackground`, `NodeType`, `NodeStack` |
| `layerstack/navigation.html` | `get_root_layer_nodes`, `get_selected_nodes`, `set_selected_nodes` |
| `textureset/textureset.html` | `TextureSet`, `has_uv_tiles`, `get_resolution`, `MeshMapUsage` |
| `textureset/stack.html` | `get_active_stack`, `all_channels` |
| `textureset/channel.html` | `ChannelType` enum |
| `resource.html` | `import_project_resource`, `search`, `Usage` |
| `event.html` | `DISPATCHER`, `BakingProcessEnded` |
| `ui.html` | `get_main_window`, `add_menu`, `UIMode` |
| `changelog.html` | Changements d'API par version de Painter |

To read a page, use the Read tool with the absolute path, e.g. `C:/Program Files/Adobe/Adobe Substance 3D Painter/resources/python-doc/substance_painter/baking.html`.

## Key Conventions

- All modules guard `substance_painter` calls behind `project.is_open()` checks or assume a project is open — always verify before calling stack/layer APIs.
- Channel type strings match `textureset.ChannelType` enum names (e.g., `"BaseColor"`, `"Height"`, `"AO"`). The export pipeline maps `"AO"` ↔ `"ambientOcclusion"` for the export config format.
- `LayerManager.add_layer()` accepts `layer_position="Above"` (above current selection) or `"On Top"` (top of stack).
- Passing `active_channels=[""]` to `add_layer()` creates a fill layer with no channels enabled; passing `None` enables all stack channels.
- `BlendingMode(2)` = Normal blend; `BlendingMode(25)` = Normal blend used for ref-point layers.
- The `ResourceCleaner` class and `delete_texture_files()` calls are intentionally disabled (commented out) in `TextureAssignmentManager` — do not re-enable without understanding the import/cleanup lifecycle.

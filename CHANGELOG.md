# Changelog

## [1.8.0] - 2026-04-19

### Collections — Batch Apply ⚡

- New **Batch Apply** feature: applies a collection's Smart Material to every Texture Set in every `.spp` project found in a selected folder, fully automated.
- Each project is opened, the Smart Material is inserted into all Texture Sets, the project is saved, then closed before moving to the next.
- Auto-saves (files whose name contains "autosave") are automatically excluded from the batch.
- A two-phase dialog guides the user: folder selection with live `.spp` count, then a live progress log (✓/✗ per project) with a Cancel button.
- New option **"Replace collection if already present"** (unchecked by default): before inserting, removes *all* root groups whose name matches the collection — handles the case where the batch was run multiple times without the option enabled.
- The `⚡` button is added to every collection row with tooltip *"Batch Apply (Apply this collection to multiple projects)"*.
- A `.spsm` existence check is performed before the batch starts, with a clear error message if the Smart Material has not been saved yet.
- The confirmation dialog is concise: collection name, project count, and folder path — no alarmist wording.

### Collections — panel auto-refresh

- The Collections panel now listens to `ProjectEditionEntered` and `ProjectClosed` events and refreshes automatically, so the **▶ Load** button reflects the correct enabled state as soon as a project is opened or closed (previously the button stayed disabled until the panel was reopened).
- Event handlers are properly disconnected on `close_plugin()` and `reload_plugin()` to prevent stale callbacks after a plugin reload.

### Bug fixes

- `BatchCollectionApplicator`: `self._replace` is now initialized in `__init__` (previously only set in `start()`).
- `BatchCollectionApplicator`: `project.close()` is now wrapped in a `try/except` to prevent an unhandled exception if the project was already closed following a processing error.

### README

- Full rewrite: installation, all features with shortcut table, Collections workflow, Batch Apply instructions, Settings and About sections.
- Added PayPal donation link.

## [1.7.0] - 2026-04-18

## [1.6.2] - 2026-04-17

### Collections — Improved creation workflow
- After filling in collection metadata, clicking "Setup Collection Content" now immediately
  generates the layer group structure in the active texture set.
- A compact floating toast overlay appears in the viewport, allowing the user to finalize
  and save the collection as a Smart Material once the layer content is ready.
- The toast overlay is frameless, dark-themed, draggable, and positioned in the upper
  viewport area. Closing it without saving prompts to Save, Discard, or Cancel.
- The Collections panel now refreshes automatically when a Smart Material is saved from
  the overlay, enabling the Load (▶) button immediately.

### About dialog
- Added "About VG Utilities…" entry at the bottom of the VG Utilities menu.
- Displays installed version, author, copyright, and MIT license with a link to GitHub.
- Includes a "Check for Updates" button that queries the GitHub API and reports whether
  the installed version is up to date.
- A silent background update check runs 8 seconds after Painter startup; if a newer
  version is available, a message is logged to the Painter console (no popup).

### Project
- Added VERSION file for version tracking.
- Added CHANGELOG.md.
- Updated .gitignore to exclude local config, IDE files, and Python cache.

## [1.6.0] - 2026-04-16

- Initial tracked release.

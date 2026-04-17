# Changelog

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

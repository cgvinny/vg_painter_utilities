##########################################################################
#
# Copyright 2024-2026 Vincent GAULT - Adobe
# All Rights Reserved.
#
##########################################################################

"""
About dialog and update-check utilities for VG Painter Utilities.
"""

__author__ = "Vincent GAULT - Adobe"

import json
import pathlib
import urllib.request

from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt

from substance_painter import ui, logging


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO          = "cgvinny/vg_painter_utilities"
_REPO_URL      = "https://github.com/cgvinny/vg_painter_utilities"
_RELEASES_URL  = "https://github.com/cgvinny/vg_painter_utilities/releases"
_LICENSE_URL   = "https://github.com/cgvinny/vg_painter_utilities/blob/main/LICENSE"
_API_LATEST    = f"https://api.github.com/repos/{_REPO}/releases/latest"

_VERSION_FILE  = pathlib.Path(__file__).parent.parent.parent / "VERSION"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_version() -> str:
    """Return the installed version string from the VERSION file."""
    try:
        return _VERSION_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        return "unknown"


def _parse_version(tag: str) -> tuple:
    return tuple(int(x) for x in tag.lstrip("v").split("."))


def check_for_update() -> dict | None:
    """
    Query the GitHub API for the latest release.

    Returns a dict with keys 'version', 'url', 'is_newer',
    or None if the check fails (network error, timeout, …).
    """
    try:
        req = urllib.request.Request(
            _API_LATEST,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "vg-painter-utils",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())

        tag = data.get("tag_name", "")
        url = data.get("html_url", _RELEASES_URL)
        current = _parse_version(read_version())
        latest  = _parse_version(tag)

        return {
            "version":  tag.lstrip("v"),
            "url":      url,
            "is_newer": latest > current,
        }
    except Exception as e:
        logging.warning(f"VG About: update check failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

class _UpdateWorker(QtCore.QThread):
    """Runs the update check off the main thread."""

    finished = QtCore.Signal(object)   # emits dict | None

    def run(self):
        self.finished.emit(check_for_update())


# ---------------------------------------------------------------------------
# About dialog
# ---------------------------------------------------------------------------

class AboutDialog(QtWidgets.QDialog):
    """
    Modal About dialog showing version, author, license and an
    on-demand update checker that queries GitHub.
    """

    def __init__(self, parent=None):
        super().__init__(parent or ui.get_main_window())
        self.setWindowTitle("About VG Painter Utilities")
        self.setFixedWidth(400)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._worker: _UpdateWorker | None = None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ---- Header band ----
        header = QtWidgets.QWidget()
        header.setStyleSheet("background-color: #1a1a1c;")
        h_layout = QtWidgets.QVBoxLayout(header)
        h_layout.setContentsMargins(24, 20, 24, 18)
        h_layout.setSpacing(4)

        title_lbl = QtWidgets.QLabel("VG Painter Utilities")
        title_lbl.setStyleSheet(
            "color: #e0e0e0; font-size: 17px; font-weight: bold; background: transparent;"
        )
        h_layout.addWidget(title_lbl)

        version_lbl = QtWidgets.QLabel(f"Version {read_version()}")
        version_lbl.setStyleSheet("color: #888; font-size: 11px; background: transparent;")
        h_layout.addWidget(version_lbl)

        root.addWidget(header)

        # ---- Body ----
        body = QtWidgets.QWidget()
        b_layout = QtWidgets.QVBoxLayout(body)
        b_layout.setContentsMargins(24, 16, 24, 16)
        b_layout.setSpacing(8)

        author_lbl = QtWidgets.QLabel("Vincent GAULT — Adobe")
        author_lbl.setStyleSheet("color: #c0c0c0; font-size: 11px;")
        b_layout.addWidget(author_lbl)

        copy_lbl = QtWidgets.QLabel("© 2024–2026 Vincent GAULT. All rights reserved.")
        copy_lbl.setStyleSheet("color: #777; font-size: 10px;")
        b_layout.addWidget(copy_lbl)

        license_lbl = QtWidgets.QLabel(
            f'Licensed under the <b>MIT License</b>'
            f' — <a href="{_LICENSE_URL}" style="color: #6aabdc;">details on GitHub</a>'
        )
        license_lbl.setTextFormat(Qt.RichText)
        license_lbl.setOpenExternalLinks(True)
        license_lbl.setStyleSheet("color: #777; font-size: 10px;")
        b_layout.addWidget(license_lbl)

        b_layout.addWidget(self._separator())

        # ---- Links ----
        links_row = QtWidgets.QHBoxLayout()
        links_row.setSpacing(6)

        for label, url in [("GitHub Repository", _REPO_URL), ("Releases", _RELEASES_URL)]:
            btn = QtWidgets.QPushButton(label)
            btn.setFlat(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { color: #6aabdc; font-size: 10px; border: none; "
                "text-decoration: underline; padding: 0; }"
                "QPushButton:hover { color: #90c8f0; }"
            )
            btn.clicked.connect(lambda _=False, u=url: QtGui.QDesktopServices.openUrl(QtCore.QUrl(u)))
            links_row.addWidget(btn)

            dot = QtWidgets.QLabel("·")
            dot.setStyleSheet("color: #555; font-size: 10px;")
            links_row.addWidget(dot)

        links_row.itemAt(links_row.count() - 1).widget().hide()  # hide trailing dot
        links_row.addStretch()
        b_layout.addLayout(links_row)

        b_layout.addWidget(self._separator())

        # ---- Update check ----
        update_row = QtWidgets.QHBoxLayout()
        update_row.setSpacing(10)

        self._check_btn = QtWidgets.QPushButton("Check for Updates")
        self._check_btn.setFixedHeight(26)
        self._check_btn.setCursor(Qt.PointingHandCursor)
        self._check_btn.clicked.connect(self._run_check)
        update_row.addWidget(self._check_btn)

        self._update_lbl = QtWidgets.QLabel()
        self._update_lbl.setTextFormat(Qt.RichText)
        self._update_lbl.setOpenExternalLinks(True)
        self._update_lbl.setStyleSheet("font-size: 10px;")
        update_row.addWidget(self._update_lbl, 1)

        b_layout.addLayout(update_row)

        # ---- Close button ----
        b_layout.addWidget(self._separator())
        btn_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        btn_box.rejected.connect(self.accept)
        b_layout.addWidget(btn_box)

        root.addWidget(body)

    @staticmethod
    def _separator() -> QtWidgets.QFrame:
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        sep.setFrameShadow(QtWidgets.QFrame.Plain)
        sep.setStyleSheet("color: #2e2e30;")
        return sep

    # ------------------------------------------------------------------
    # Update check
    # ------------------------------------------------------------------

    def _run_check(self):
        self._check_btn.setEnabled(False)
        self._update_lbl.setText('<font color="#888"><i>Checking…</i></font>')
        self._worker = _UpdateWorker()
        self._worker.finished.connect(self._on_check_done)
        self._worker.start()

    def _on_check_done(self, result: dict | None):
        self._check_btn.setEnabled(True)
        if result is None:
            self._update_lbl.setText('<font color="#888">Could not reach GitHub.</font>')
        elif result["is_newer"]:
            self._update_lbl.setText(
                f'<font color="#f0a030">&#9679; Version {result["version"]} available — </font>'
                f'<a href="{result["url"]}" style="color: #6aabdc;">Download</a>'
            )
        else:
            self._update_lbl.setText('<font color="#55aa55">&#10003; You are up to date.</font>')

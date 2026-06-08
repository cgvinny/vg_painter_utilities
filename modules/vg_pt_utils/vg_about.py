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

# imported lazily to avoid circular imports at module load time
def _vg_settings():
    from vg_pt_utils import vg_settings
    return vg_settings


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO          = "cgvinny/vg_painter_utilities"
_REPO_URL      = "https://github.com/cgvinny/vg_painter_utilities"
_RELEASES_URL  = "https://github.com/cgvinny/vg_painter_utilities/releases"
_LICENSE_URL   = "https://github.com/cgvinny/vg_painter_utilities/blob/main/LICENSE"
_API_LATEST    = f"https://api.github.com/repos/{_REPO}/releases/latest"

def _find_version_file() -> pathlib.Path:
    # Resolve first to handle symlinks and normalise __pycache__ .pyc paths.
    base = pathlib.Path(__file__).resolve()
    # Walk up until we find a directory that contains "VERSION", up to 5 levels.
    for _ in range(5):
        base = base.parent
        candidate = base / "VERSION"
        if candidate.exists():
            return candidate
    # Fallback: expected location relative to module (may not exist)
    return pathlib.Path(__file__).resolve().parent.parent.parent / "VERSION"

_VERSION_FILE = _find_version_file()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_version() -> str:
    """Return the installed version string from the VERSION file."""
    try:
        return _VERSION_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        logging.warning(f"VG About: VERSION file not found at '{_VERSION_FILE}'")
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
        self.setWindowFlags(
            (self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            | Qt.WindowCloseButtonHint
        )
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
            self._update_lbl.setText(
                '<font color="#888">Could not reach GitHub.<br>'
                'Check your network or firewall settings.</font>'
            )
        elif result["is_newer"]:
            self._update_lbl.setText(
                f'<font color="#f0a030">&#9679; Version {result["version"]} available — </font>'
                f'<a href="{result["url"]}" style="color: #6aabdc;">Download</a>'
            )
        else:
            self._update_lbl.setText('<font color="#55aa55">&#10003; You are up to date.</font>')


# ---------------------------------------------------------------------------
# Startup update toast
# ---------------------------------------------------------------------------

class UpdateToast(QtWidgets.QWidget):
    """
    Small non-blocking banner shown once at startup when a new version is
    available. Auto-dismisses after ``_TIMEOUT_MS`` milliseconds, or can be
    closed manually. A "don't show again for this version" checkbox lets
    production users suppress the banner until the next release.
    """

    _TIMEOUT_MS = 12_000

    def __init__(self, version: str, url: str, parent=None):
        super().__init__(parent or ui.get_main_window())
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._version = version
        self._build_ui(version, url)
        self._position()

        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._close_and_save)
        self._timer.start(self._TIMEOUT_MS)

    def _build_ui(self, version: str, url: str):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(14, 10, 10, 10)
        root.setSpacing(6)

        self.setStyleSheet(
            "UpdateToast { background: #2a2000; border: 1px solid #f0a030; border-radius: 6px; }"
        )

        # -- Top row: icon + text + close button --
        top_row = QtWidgets.QHBoxLayout()
        top_row.setSpacing(12)

        icon_lbl = QtWidgets.QLabel("🔔")
        icon_lbl.setStyleSheet("background: transparent; font-size: 16px;")
        top_row.addWidget(icon_lbl)

        text_lbl = QtWidgets.QLabel(
            f'<span style="color:#f0a030; font-weight:bold;">VG Utilities {version} available</span><br>'
            f'<a href="{url}" style="color:#6aabdc;">Download on GitHub</a>'
        )
        text_lbl.setTextFormat(Qt.RichText)
        text_lbl.setOpenExternalLinks(True)
        text_lbl.setStyleSheet("background: transparent; font-size: 11px;")
        top_row.addWidget(text_lbl, 1)

        close_btn = QtWidgets.QPushButton("✕")
        close_btn.setFixedSize(20, 20)
        close_btn.setFlat(True)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { color: #888; background: transparent; border: none; font-size: 12px; }"
            "QPushButton:hover { color: #e0e0e0; }"
        )
        close_btn.clicked.connect(self._close_and_save)
        top_row.addWidget(close_btn)
        root.addLayout(top_row)

        # -- Bottom row: snooze checkbox --
        self._snooze_cb = QtWidgets.QCheckBox("Don't show again for this version")
        self._snooze_cb.setStyleSheet(
            "QCheckBox { color: #777; font-size: 10px; background: transparent; }"
            "QCheckBox::indicator { width: 11px; height: 11px; }"
        )
        root.addWidget(self._snooze_cb)

        self.adjustSize()

    def _close_and_save(self):
        if self._snooze_cb.isChecked():
            s = _vg_settings()
            settings = s.load_settings()
            settings["update_toast_snoozed_version"] = self._version
            s.save_settings(settings)
        self.close()

    def _position(self):
        parent = self.parentWidget()
        if parent:
            pr = parent.geometry()
            self.move(pr.right() - self.width() - 20, pr.bottom() - self.height() - 40)
        else:
            screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
            self.move(screen.right() - self.width() - 20, screen.bottom() - self.height() - 40)


def show_startup_toast(version: str, url: str) -> UpdateToast:
    """
    Show the update toast, unless the user already snoozed this exact version.
    Returns the widget, or None if suppressed.
    """
    s = _vg_settings()
    settings = s.load_settings()
    if settings.get("update_toast_snoozed_version") == version:
        return None
    toast = UpdateToast(version, url)
    toast.show()
    return toast

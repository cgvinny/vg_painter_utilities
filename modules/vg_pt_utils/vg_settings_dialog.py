##########################################################################
#
# Copyright 2010-2024 Vincent GAULT - Adobe
# All Rights Reserved.
#
##########################################################################

"""
Settings dialog for VG Utilities.
Provides keyboard shortcut customisation and general preferences,
with live conflict detection against both Painter's built-in shortcuts
and shortcuts defined within the plugin.
"""
__author__ = "Vincent GAULT - Adobe"

import string
from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import Qt
from substance_painter import ui
from vg_pt_utils import vg_settings

_KEYS = list(string.ascii_uppercase) + [str(i) for i in range(10)]


class SettingsDialog(QtWidgets.QDialog):
    """
    Two-page settings dialog:
      - Keyboard Shortcuts: modifier + key picker per action, live conflict badges.
      - General: reference point layer name prefix.
    """

    def __init__(self, parent=None):
        super().__init__(parent or ui.get_main_window())
        self.setWindowTitle("VG Utilities – Settings")
        self.setMinimumSize(780, 500)
        self._settings = vg_settings.load_settings()
        self._rows = {}  # action_id -> (mod_combo, key_combo, status_lbl)
        self._painter_shortcuts = self._collect_painter_shortcuts()
        self._build_ui()
        self._validate_all()

    # ------------------------------------------------------------------
    # Painter shortcut discovery
    # ------------------------------------------------------------------

    def _collect_painter_shortcuts(self):
        """
        Return {shortcut_lower: action_text} for every QAction registered in
        Painter's main window, excluding our own plugin actions.
        """
        our_labels = set(vg_settings.ACTION_LABELS.values()) | {"Settings..."}
        result = {}
        for action in ui.get_main_window().findChildren(QtGui.QAction):
            if action.text().strip() in our_labels:
                continue
            for seq in action.shortcuts():
                s = seq.toString()
                if s:
                    result[s.lower()] = action.text() or "(unnamed)"
        return result

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)

        # Horizontal split: nav sidebar | stacked pages
        body = QtWidgets.QHBoxLayout()

        self._nav = QtWidgets.QListWidget()
        self._nav.setFixedWidth(165)
        self._nav.addItems(["Keyboard Shortcuts", "General"])
        self._nav.setCurrentRow(0)
        self._nav.currentRowChanged.connect(self._on_nav_changed)
        body.addWidget(self._nav)

        # Vertical separator line
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.VLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        body.addWidget(line)

        self._pages = QtWidgets.QStackedWidget()
        self._pages.addWidget(self._build_shortcuts_page())
        self._pages.addWidget(self._build_general_page())
        body.addWidget(self._pages, 1)
        root.addLayout(body)

        # Save / Cancel
        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        btn_box.accepted.connect(self._on_save)
        btn_box.rejected.connect(self.reject)
        root.addWidget(btn_box)

    def _build_shortcuts_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 4)

        header_row = QtWidgets.QHBoxLayout()
        header_row.addWidget(QtWidgets.QLabel("<b>Keyboard Shortcuts</b>"))
        header_row.addStretch()
        restore_btn = QtWidgets.QPushButton("Restore Defaults")
        restore_btn.setToolTip("Reset all shortcuts to their factory defaults")
        restore_btn.clicked.connect(self._restore_defaults)
        header_row.addWidget(restore_btn)
        layout.addLayout(header_row)

        legend = QtWidgets.QLabel(
            '<font color="#55aa55">&#10003;</font> OK &nbsp;&nbsp;'
            '<font color="#e07b39">&#9888;</font> Potential conflict &nbsp;&nbsp;'
            '<font color="#cc4444">&#10006;</font> Conflict within plugin'
        )
        legend.setTextFormat(Qt.RichText)
        layout.addWidget(legend)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

        inner = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(inner)
        grid.setColumnStretch(0, 4)
        grid.setColumnStretch(1, 2)
        grid.setColumnStretch(2, 0)
        grid.setColumnStretch(3, 2)
        grid.setColumnStretch(4, 3)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)

        # Header row
        for col, text in enumerate(["Action", "Modifier", "", "Key", "Status"]):
            lbl = QtWidgets.QLabel(f"<b>{text}</b>")
            grid.addWidget(lbl, 0, col)

        modifier_items = [vg_settings.MODIFIER_DISPLAY[m] for m in vg_settings.MODIFIER_OPTIONS]

        for row_idx, (action_id, label) in enumerate(vg_settings.ACTION_LABELS.items(), start=1):
            sc = self._settings["shortcuts"].get(action_id, {"modifier": "", "key": ""})

            grid.addWidget(QtWidgets.QLabel(label), row_idx, 0)

            mod_combo = QtWidgets.QComboBox()
            mod_combo.addItems(modifier_items)
            mod_display = vg_settings.MODIFIER_DISPLAY.get(sc.get("modifier", ""), "(none)")
            mod_combo.setCurrentText(mod_display)
            grid.addWidget(mod_combo, row_idx, 1)

            grid.addWidget(QtWidgets.QLabel("+"), row_idx, 2)

            key_combo = QtWidgets.QComboBox()
            key_combo.addItems(["(none)"] + _KEYS)
            current_key = sc.get("key", "").upper()
            key_combo.setCurrentText(current_key if current_key in _KEYS else "(none)")
            grid.addWidget(key_combo, row_idx, 3)

            status_lbl = QtWidgets.QLabel()
            status_lbl.setTextFormat(Qt.RichText)
            grid.addWidget(status_lbl, row_idx, 4)

            self._rows[action_id] = (mod_combo, key_combo, status_lbl)
            mod_combo.currentIndexChanged.connect(self._validate_all)
            key_combo.currentIndexChanged.connect(self._validate_all)

        scroll.setWidget(inner)
        layout.addWidget(scroll)
        return page

    def _build_general_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 4)

        layout.addWidget(QtWidgets.QLabel("<b>General</b>"))

        form = QtWidgets.QFormLayout()
        form.setRowWrapPolicy(QtWidgets.QFormLayout.DontWrapRows)

        prefix = self._settings.get("ref_point", {}).get("default_name_prefix", "REF POINT LAYER")
        self._ref_prefix = QtWidgets.QLineEdit(prefix)
        self._ref_prefix.setMaximumWidth(300)
        form.addRow("Reference point name prefix:", self._ref_prefix)

        note = QtWidgets.QLabel(
            '<i>This prefix is used as the base name for new reference point layers.<br>'
            'Example: "REF POINT LAYER" produces "REF POINT LAYER_01", "REF POINT LAYER_02"…</i>'
        )
        note.setWordWrap(True)
        note.setTextFormat(Qt.RichText)
        form.addRow(note)
        layout.addLayout(form)
        layout.addStretch()
        return page

    # ------------------------------------------------------------------
    # Conflict validation
    # ------------------------------------------------------------------

    def _validate_all(self):
        """Recompute and display conflict status for every shortcut row."""
        # Map shortcut string -> [action_ids] for all currently set shortcuts
        seen = {}
        for action_id, (mod_combo, key_combo, _) in self._rows.items():
            sc = self._shortcut_from_row(mod_combo, key_combo)
            if sc:
                seen.setdefault(sc.lower(), []).append(action_id)

        for action_id, (mod_combo, key_combo, status_lbl) in self._rows.items():
            sc = self._shortcut_from_row(mod_combo, key_combo)
            if not sc:
                status_lbl.setText("")
                continue

            sc_lower = sc.lower()
            duplicates = [a for a in seen.get(sc_lower, []) if a != action_id]

            raw_mod = next(
                (k for k, v in vg_settings.MODIFIER_DISPLAY.items()
                 if v == mod_combo.currentText()), ""
            )
            is_bare_shift  = (raw_mod == "Shift")
            is_no_modifier = (raw_mod == "")

            if duplicates:
                other = vg_settings.ACTION_LABELS.get(duplicates[0], duplicates[0])
                status_lbl.setText(
                    f'<font color="#cc4444">&#10006; "{other}"</font>'
                )
            elif sc_lower in self._painter_shortcuts:
                other = self._painter_shortcuts[sc_lower]
                status_lbl.setText(
                    f'<font color="#e07b39">&#9888; "{other}"</font>'
                )
            elif is_no_modifier:
                status_lbl.setText(
                    '<font color="#e07b39">&#9888; May conflict with Painter\'s tool keys</font>'
                )
            elif is_bare_shift:
                status_lbl.setText(
                    '<font color="#e07b39">&#9888; Painter may intercept Shift alone</font>'
                )
            else:
                status_lbl.setText('<font color="#55aa55">&#10003;</font>')

    def _shortcut_from_row(self, mod_combo, key_combo):
        """Convert a row's combo selections to a QKeySequence-compatible string."""
        mod_display = mod_combo.currentText()
        key = key_combo.currentText()
        if key == "(none)":
            return ""
        # Reverse the display mapping to recover the raw modifier string
        raw_mod = next(
            (k for k, v in vg_settings.MODIFIER_DISPLAY.items() if v == mod_display), ""
        )
        return vg_settings.build_shortcut_string(raw_mod, key)

    # ------------------------------------------------------------------
    # Navigation, restore and save
    # ------------------------------------------------------------------

    def _restore_defaults(self):
        """Reset all shortcut combo boxes to factory defaults."""
        defaults = vg_settings.DEFAULT_SETTINGS["shortcuts"]
        for action_id, (mod_combo, key_combo, _) in self._rows.items():
            sc = defaults.get(action_id, {"modifier": "", "key": ""})
            mod_display = vg_settings.MODIFIER_DISPLAY.get(sc.get("modifier", ""), "(none)")
            mod_combo.setCurrentText(mod_display)
            key = sc.get("key", "").upper()
            key_combo.setCurrentText(key if key in _KEYS else "(none)")
        self._validate_all()

    def _on_nav_changed(self, index):
        self._pages.setCurrentIndex(index)

    def _on_save(self):
        for action_id, (mod_combo, key_combo, _) in self._rows.items():
            mod_display = mod_combo.currentText()
            raw_mod = next(
                (k for k, v in vg_settings.MODIFIER_DISPLAY.items() if v == mod_display), ""
            )
            key = key_combo.currentText()
            self._settings["shortcuts"][action_id] = {
                "modifier": raw_mod,
                "key": "" if key == "(none)" else key,
            }
        self._settings["ref_point"]["default_name_prefix"] = (
            self._ref_prefix.text().strip() or "REF POINT LAYER"
        )
        vg_settings.save_settings(self._settings)
        self.accept()

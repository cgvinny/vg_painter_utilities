###############################################################################
# This script creates a menu to host different tools for Substance 3D Painter
# ___________________
# Copyright 2024 Vincent GAULT - Adobe
# All Rights Reserved.
###############################################################################

"""
This module creates a menu to host various tools for Substance Painter.
"""

__author__ = "Vincent GAULT - Adobe"

# Modules import
from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import QTimer
from PySide6.QtGui import QKeySequence
import importlib

from substance_painter import ui, logging
from vg_pt_utils import vg_baking, vg_export, vg_layerstack, vg_project_info, vg_settings, vg_collection, vg_about, vg_palette

plugin_menus_widgets = []
"""Keeps track of added UI elements for cleanup."""

_mask_popup_menu = None
"""Module-level reference to the mask popup menu, prevents garbage collection."""

_collection_panel = None
"""The CollectionPanel widget instance — kept alive to prevent garbage collection."""

_collection_dock = None
"""The QDockWidget wrapping the panel, returned by ui.add_dock_widget()."""

_palette_panel = None
"""The PalettePanel widget instance — kept alive to prevent garbage collection."""

_palette_dock = None
"""The QDockWidget wrapping the palette panel, returned by ui.add_dock_widget()."""

_startup_update_worker = None
"""Background thread for the silent startup update check."""

### FILL LAYER FUNCTIONS ###

def new_fill_layer_base():
    """Create a new fill layer with Base Color activated."""
    layer_manager = vg_layerstack.LayerManager()
    layer_manager.add_layer(layer_type='fill', active_channels=["BaseColor"], layer_name="New fill layer")

def new_fill_layer_height():
    """Create a new fill layer with Height channel activated."""
    layer_manager = vg_layerstack.LayerManager()
    layer_manager.add_layer(layer_type='fill', active_channels=["Height"], layer_name="New fill layer")

def new_fill_layer_all():
    """Create a new fill layer with all channels activated."""
    layer_manager = vg_layerstack.LayerManager()
    layer_manager.add_layer(layer_type='fill', layer_name="New fill layer")
    

def new_fill_layer_empty():
    """Create a new fill layer with no channels activated."""
    layer_manager = vg_layerstack.LayerManager()
    layer_manager.add_layer(layer_type='fill', active_channels=[""], layer_name="New fill layer")


### PAINT LAYER FUNCTIONS ###

def new_paint_layer():
    """Create a new paint layer."""
    layer_manager = vg_layerstack.LayerManager()
    layer_manager.add_layer(layer_type='paint', layer_name="New Paint layer")

### MASK FUNCTIONS ###

def add_mask_popup():
    """Open a popup menu to choose the type of mask to add to the selected layer."""
    global _mask_popup_menu

    layer_manager = vg_layerstack.LayerManager()
    mask_manager = vg_layerstack.MaskManager(layer_manager)

    _mask_popup_menu = QtWidgets.QMenu(ui.get_main_window())
    _mask_popup_menu.addAction("Black Mask",                    lambda: mask_manager.add_mask('Black'))
    _mask_popup_menu.addAction("White Mask",                    lambda: mask_manager.add_mask('White'))
    _mask_popup_menu.addSeparator()
    _mask_popup_menu.addAction("Mask with Fill Effect",          mask_manager.add_mask_with_fill)
    _mask_popup_menu.addAction("Mask with Paint Layer",          mask_manager.add_mask_with_paint)
    _mask_popup_menu.addSeparator()
    _mask_popup_menu.addAction("Mask with AO Generator",         mask_manager.add_black_mask_with_ao_generator)
    _mask_popup_menu.addAction("Mask with Curvature Generator",  mask_manager.add_black_mask_with_curvature_generator)
    _mask_popup_menu.addSeparator()
    _mask_popup_menu.addAction("Mask with Levels",               mask_manager.add_mask_with_levels)
    _mask_popup_menu.addAction("Mask with Compare Mask",         mask_manager.add_mask_with_compare_mask)
    _mask_popup_menu.addAction("Mask with Color Selection",      mask_manager.add_mask_with_color_selection)

    pos = QtGui.QCursor.pos()
    QTimer.singleShot(100, lambda: _mask_popup_menu.exec(pos))


### GENERATE CONTENT FROM STACK ###

def create_layer_from_stack():
    """Generate a layer from the visible content in the stack."""
    vg_export.create_layer_from_stack()


def create_layer_from_group():
    """Generate a fill layer from the selected group's isolated content."""
    vg_export.create_layer_from_group()


def create_id_map_from_group():
    """Export the selected group as an ID map and assign it to the ID mesh map slot."""
    vg_export.create_id_map_from_group()


def id_color_swap():
    """Open a dialog to pick source and target colors, then swap them in the ID map."""
    from PySide6 import QtGui, QtCore
    from substance_painter import colormanagement

    class _IDColorSwapDialog(QtWidgets.QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("ID Color Swap")
            self.setFixedWidth(280)
            self._source = QtGui.QColor.fromRgbF(1.0, 0.0, 0.0)
            self._target = QtGui.QColor.fromRgbF(0.0, 1.0, 0.0)

            layout = QtWidgets.QVBoxLayout(self)
            layout.setSpacing(12)

            swatches = QtWidgets.QHBoxLayout()
            swatches.setSpacing(16)

            self._src_btn = self._make_swatch_column(swatches, "Current color", self._source)
            self._tgt_btn = self._make_swatch_column(swatches, "New color", self._target)
            layout.addLayout(swatches)

            self._src_btn.clicked.connect(self._pick_source)
            self._tgt_btn.clicked.connect(self._pick_target)

            layout.addSpacing(4)

            swap_btn = QtWidgets.QPushButton("Swap Color")
            swap_btn.setDefault(True)
            swap_btn.clicked.connect(self.accept)
            cancel_btn = QtWidgets.QPushButton("Cancel")
            cancel_btn.clicked.connect(self.reject)

            btn_row = QtWidgets.QHBoxLayout()
            btn_row.addWidget(cancel_btn)
            btn_row.addWidget(swap_btn)
            layout.addLayout(btn_row)

        def _make_swatch_column(self, parent_layout, label_text, color):
            col = QtWidgets.QVBoxLayout()
            col.setSpacing(4)
            lbl = QtWidgets.QLabel(label_text)
            lbl.setAlignment(QtCore.Qt.AlignCenter)
            btn = QtWidgets.QPushButton()
            btn.setFixedSize(100, 60)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            self._apply_color(btn, color)
            col.addWidget(lbl)
            col.addWidget(btn)
            parent_layout.addLayout(col)
            return btn

        @staticmethod
        def _apply_color(btn, qcolor):
            pix = QtGui.QPixmap(btn.width() or 100, btn.height() or 60)
            pix.fill(qcolor)
            btn.setIcon(QtGui.QIcon(pix))
            btn.setIconSize(btn.size())

        def _pick_source(self):
            qc = QtWidgets.QColorDialog.getColor(
                self._source, self, "Current Color",
                QtWidgets.QColorDialog.DontUseNativeDialog,
            )
            if qc.isValid():
                self._source = qc
                self._apply_color(self._src_btn, qc)

        def _pick_target(self):
            qc = QtWidgets.QColorDialog.getColor(
                self._target, self, "New Color",
                QtWidgets.QColorDialog.DontUseNativeDialog,
            )
            if qc.isValid():
                self._target = qc
                self._apply_color(self._tgt_btn, qc)

        def source_color(self):
            return colormanagement.Color(self._source.redF(), self._source.greenF(), self._source.blueF())

        def target_color(self):
            return colormanagement.Color(self._target.redF(), self._target.greenF(), self._target.blueF())

    dlg = _IDColorSwapDialog(ui.get_main_window())
    if dlg.exec() == QtWidgets.QDialog.Accepted:
        vg_export.swap_id_map_color(dlg.source_color(), dlg.target_color())


def flatten_stack():
    """Flatten the stack by exporting and importing textures."""
    vg_export.flatten_stack()


### CREATE REFERENCE POINT LAYER ###

def create_ref_point_layer():
    """Prompt for a name and create a reference point layer."""
    prefix = vg_settings.load_settings().get("ref_point", {}).get(
        "default_name_prefix", "REF POINT LAYER"
    )
    stack_manager = vg_layerstack.LayerManager()
    default_name = stack_manager.get_next_ref_point_name(base_name=prefix)

    name, ok = QtWidgets.QInputDialog.getText(
        ui.get_main_window(),
        "Create Reference Point Layer",
        "Layer name:",
        text=default_name
    )

    if ok and name.strip():
        stack_manager.generate_ref_point_layer(layer_name=name.strip())


### COLLECTIONS ###

def _save_collection_panel_state(visible: bool):
    """Persist the Collections panel open/closed state to settings."""
    settings = vg_settings.load_settings()
    settings["collection_panel_open"] = visible
    vg_settings.save_settings(settings)


def open_collections_panel():
    """Open (or raise) the unified Collections dockable panel."""
    global _collection_panel, _collection_dock

    # If the dock already exists and is alive, just show/raise it
    if _collection_dock is not None:
        try:
            _collection_dock.show()
            _collection_dock.raise_()
            return
        except RuntimeError:
            # Widget was deleted externally — fall through to recreate
            _collection_dock = None
            _collection_panel = None

    from vg_pt_utils.vg_collection_dialog import CollectionPanel
    _collection_panel = CollectionPanel()
    _collection_dock = ui.add_dock_widget(_collection_panel)
    plugin_menus_widgets.append(_collection_dock)

    _collection_dock.visibilityChanged.connect(_save_collection_panel_state)
    _save_collection_panel_state(True)


### PALETTE ###

def _save_palette_panel_state(visible: bool):
    """Persist the Base Color Manager panel open/closed state to settings."""
    settings = vg_settings.load_settings()
    settings["palette_panel_open"] = visible
    vg_settings.save_settings(settings)


def open_palette_panel():
    """Open (or raise) the Base Color Manager dockable panel."""
    global _palette_panel, _palette_dock

    if _palette_dock is not None:
        try:
            _palette_dock.show()
            _palette_dock.raise_()
            _palette_panel.refresh()
            return
        except RuntimeError:
            _palette_dock = None
            _palette_panel = None

    _palette_panel = vg_palette.PalettePanel()
    _palette_dock = ui.add_dock_widget(_palette_panel)
    plugin_menus_widgets.append(_palette_dock)

    _palette_dock.visibilityChanged.connect(_save_palette_panel_state)
    _save_palette_panel_state(True)


### QUICK BAKE ###

def launch_quick_bake():
    """Bake mesh maps of the current texture set."""
    vg_baking.quick_bake()

def launch_bake_all():
    """Bake mesh maps for all texture sets in the project."""
    vg_baking.bake_all_texture_sets()


### ABOUT ###

def open_about():
    """Open the About dialog."""
    from vg_pt_utils.vg_about import AboutDialog
    dlg = AboutDialog(ui.get_main_window())
    dlg.exec()


def _run_startup_update_check():
    """Silent background update check at startup — logs to Painter console if outdated."""
    global _startup_update_worker

    from vg_pt_utils.vg_about import _UpdateWorker, _RELEASES_URL

    def _on_result(result):
        if result and result["is_newer"]:
            logging.info(
                f"VG Utilities: version {result['version']} is available — {_RELEASES_URL}"
            )

    _startup_update_worker = _UpdateWorker()
    _startup_update_worker.finished.connect(_on_result)
    _startup_update_worker.start()


### SETTINGS ###

def open_settings():
    """Open the VG Utilities settings dialog; rebuild the menu if saved."""
    from vg_pt_utils.vg_settings_dialog import SettingsDialog
    dlg = SettingsDialog(ui.get_main_window())
    if dlg.exec() == QtWidgets.QDialog.Accepted:
        # Preserve dock widgets across the menu rebuild.
        docks = [w for w in plugin_menus_widgets if w in (_collection_dock, _palette_dock)]
        menus = [w for w in plugin_menus_widgets if w not in docks]
        for widget in menus:
            ui.delete_ui_element(widget)
        plugin_menus_widgets.clear()
        plugin_menus_widgets.extend(docks)
        create_menu()


#################################################################

# Maps action IDs to their handler functions.
_ACTION_FUNCS = {
    "new_paint_layer":          lambda: new_paint_layer(),
    "new_fill_layer_base":      lambda: new_fill_layer_base(),
    "new_fill_layer_height":    lambda: new_fill_layer_height(),
    "new_fill_layer_all":       lambda: new_fill_layer_all(),
    "new_fill_layer_empty":     lambda: new_fill_layer_empty(),
    "add_mask_popup":           lambda: add_mask_popup(),
    "create_layer_from_stack":  lambda: create_layer_from_stack(),
    "create_layer_from_group":  lambda: create_layer_from_group(),
    "create_id_map_from_group":        lambda: create_id_map_from_group(),
    "id_color_swap":                   lambda: id_color_swap(),
    "palette_extractor":               lambda: open_palette_panel(),
    "flatten_stack":            lambda: flatten_stack(),
    "create_ref_point_layer":   lambda: create_ref_point_layer(),
    "launch_quick_bake":        lambda: launch_quick_bake(),
    "launch_bake_all":          lambda: launch_bake_all(),
    "collection_panel":         lambda: open_collections_panel(),
}

# Menu structure: action IDs interleaved with None for separators.
_MENU_STRUCTURE = [
    "new_paint_layer",
    None,
    "new_fill_layer_base",
    "new_fill_layer_height",
    "new_fill_layer_all",
    "new_fill_layer_empty",
    None,
    "add_mask_popup",
    None,
    "create_layer_from_stack",
    "create_layer_from_group",
    "flatten_stack",
    None,
    "create_id_map_from_group",
    "id_color_swap",
    "palette_extractor",
    None,
    "create_ref_point_layer",
    None,
    "launch_quick_bake",
    "launch_bake_all",
]


def create_menu():
    """Create and populate the VG Utilities menu, loading shortcuts from settings."""
    settings = vg_settings.load_settings()
    main_window = ui.get_main_window()

    vg_utilities_menu = QtWidgets.QMenu("VG Utilities", main_window)
    ui.add_menu(vg_utilities_menu)
    plugin_menus_widgets.append(vg_utilities_menu)

    for item in _MENU_STRUCTURE:
        if item is None:
            vg_utilities_menu.addSeparator()
        else:
            sc_data = settings["shortcuts"].get(item, {})
            sc_str = vg_settings.build_shortcut_string(
                sc_data.get("modifier", ""),
                sc_data.get("key", "")
            )
            action = QtGui.QAction(vg_settings.ACTION_LABELS[item], vg_utilities_menu)
            action.triggered.connect(_ACTION_FUNCS[item])
            if sc_str:
                action.setShortcut(QKeySequence(sc_str))
            vg_utilities_menu.addAction(action)

    # Collections panel entry
    vg_utilities_menu.addSeparator()
    sc_data = settings["shortcuts"].get("collection_panel", {})
    sc_str = vg_settings.build_shortcut_string(
        sc_data.get("modifier", ""), sc_data.get("key", "")
    )
    collections_action = QtGui.QAction("Collections…", vg_utilities_menu)
    collections_action.triggered.connect(_ACTION_FUNCS["collection_panel"])
    if sc_str:
        collections_action.setShortcut(QKeySequence(sc_str))
    vg_utilities_menu.addAction(collections_action)

    vg_utilities_menu.addSeparator()
    settings_action = QtGui.QAction("Settings...", vg_utilities_menu)
    settings_action.triggered.connect(open_settings)
    vg_utilities_menu.addAction(settings_action)

    vg_utilities_menu.addSeparator()
    about_action = QtGui.QAction("About VG Utilities…", vg_utilities_menu)
    about_action.triggered.connect(open_about)
    vg_utilities_menu.addAction(about_action)



def start_plugin():
    """Called when the plugin is started."""
    create_menu()
    vg_collection.flush_pending_deletions()
    settings = vg_settings.load_settings()
    if settings.get("collection_panel_open", False):
        QTimer.singleShot(500, open_collections_panel)
    if settings.get("palette_panel_open", False):
        QTimer.singleShot(500, open_palette_panel)
    logging.info("VG Menu Activated")
    QTimer.singleShot(8000, _run_startup_update_check)
    

def close_plugin():
    """Called when the plugin is stopped."""
    global _mask_popup_menu, _collection_panel, _collection_dock, _palette_panel, _palette_dock

    # Save panel visibility BEFORE any cleanup — shutdown signals would overwrite with False.
    settings = vg_settings.load_settings()
    if _collection_dock is not None:
        try:
            settings["collection_panel_open"] = _collection_dock.isVisible()
        except RuntimeError:
            pass
    if _palette_dock is not None:
        try:
            settings["palette_panel_open"] = _palette_dock.isVisible()
        except RuntimeError:
            pass
    vg_settings.save_settings(settings)

    # Disconnect visibility signals so the delete_ui_element calls don't overwrite the saved state.
    _mask_popup_menu = None
    if _collection_panel is not None:
        _collection_panel.cleanup()
    _collection_panel = None
    if _collection_dock is not None:
        try:
            _collection_dock.visibilityChanged.disconnect(_save_collection_panel_state)
        except RuntimeError:
            pass
    _collection_dock = None
    if _palette_panel is not None:
        try:
            _palette_panel._poll_timer.stop()
            _palette_panel._disconnect_events()
        except Exception:
            pass
    if _palette_dock is not None:
        try:
            _palette_dock.visibilityChanged.disconnect(_save_palette_panel_state)
        except RuntimeError:
            pass
    _palette_panel = None
    _palette_dock = None
    for widget in plugin_menus_widgets:
        ui.delete_ui_element(widget)
    plugin_menus_widgets.clear()
    logging.info("VG Menu deactivated")


def reload_plugin():
    """Reload plugin modules and recreate the menu."""
    global _collection_panel, _collection_dock, _palette_panel, _palette_dock

    if _palette_panel is not None:
        try:
            _palette_panel._poll_timer.stop()
            _palette_panel._disconnect_events()
        except Exception:
            pass
    if _palette_dock is not None:
        try:
            ui.delete_ui_element(_palette_dock)
            if _palette_dock in plugin_menus_widgets:
                plugin_menus_widgets.remove(_palette_dock)
        except Exception:
            pass
        _palette_dock = None
        _palette_panel = None

    # Close the panel so stale module references are dropped
    if _collection_dock is not None:
        if _collection_panel is not None:
            _collection_panel.cleanup()
        try:
            ui.delete_ui_element(_collection_dock)
            if _collection_dock in plugin_menus_widgets:
                plugin_menus_widgets.remove(_collection_dock)
        except Exception:
            pass
        _collection_dock = None
        _collection_panel = None

    importlib.reload(vg_settings)
    importlib.reload(vg_layerstack)
    importlib.reload(vg_export)
    importlib.reload(vg_baking)
    importlib.reload(vg_project_info)
    importlib.reload(vg_palette)
    importlib.reload(vg_collection)
    importlib.reload(vg_about)
    from vg_pt_utils import vg_settings_dialog
    importlib.reload(vg_settings_dialog)
    from vg_pt_utils import vg_collection_dialog
    importlib.reload(vg_collection_dialog)

if __name__ == "__main__":
    reload_plugin()
    start_plugin()

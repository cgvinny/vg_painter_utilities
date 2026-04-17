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
from vg_pt_utils import vg_baking, vg_export, vg_layerstack, vg_project_info, vg_settings, vg_collection, vg_about

plugin_menus_widgets = []
"""Keeps track of added UI elements for cleanup."""

_mask_popup_menu = None
"""Module-level reference to the mask popup menu, prevents garbage collection."""

_collection_panel = None
"""The CollectionPanel widget instance — kept alive to prevent garbage collection."""

_collection_dock = None
"""The QDockWidget wrapping the panel, returned by ui.add_dock_widget()."""

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
        for widget in plugin_menus_widgets:
            ui.delete_ui_element(widget)
        plugin_menus_widgets.clear()
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
    logging.info("VG Menu Activated")
    QTimer.singleShot(8000, _run_startup_update_check)
    

def close_plugin():
    """Called when the plugin is stopped."""
    global _mask_popup_menu, _collection_panel, _collection_dock
    _mask_popup_menu = None
    _collection_panel = None
    _collection_dock = None
    for widget in plugin_menus_widgets:
        ui.delete_ui_element(widget)
    plugin_menus_widgets.clear()
    logging.info("VG Menu deactivated")


def reload_plugin():
    """Reload plugin modules and recreate the menu."""
    global _collection_panel, _collection_dock

    # Close the panel so stale module references are dropped
    if _collection_dock is not None:
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
    importlib.reload(vg_collection)
    importlib.reload(vg_about)
    from vg_pt_utils import vg_settings_dialog
    importlib.reload(vg_settings_dialog)
    from vg_pt_utils import vg_collection_dialog
    importlib.reload(vg_collection_dialog)

if __name__ == "__main__":
    reload_plugin()
    start_plugin()

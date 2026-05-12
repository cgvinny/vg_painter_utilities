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
from functools import partial

from substance_painter import ui, logging, event
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

_auto_thumbnail_action = None
"""Checkable menu action for Auto Thumbnail — kept alive to stay in sync with the setting."""

### LAYER FUNCTIONS ###

def _new_fill_layer(active_channels=None):
    vg_layerstack.LayerManager().add_layer(layer_type='fill', active_channels=active_channels, layer_name="New fill layer")

def new_paint_layer():
    """Create a new paint layer."""
    vg_layerstack.LayerManager().add_layer(layer_type='paint', layer_name="New Paint layer")

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

def create_id_map_from_group():
    """Export the selected group as an ID map and assign it to the ID mesh map slot."""
    vg_export.create_id_map_from_group()


def save_viewport_thumbnail():
    """Grab the central viewport and save it as a PNG next to the .spp file."""
    vg_export.save_viewport_thumbnail()


def id_color_swap():
    """Open a dialog to pick source and target colors, then swap them in the ID map."""
    from vg_pt_utils.vg_export import IDColorSwapDialog
    dlg = IDColorSwapDialog(ui.get_main_window())
    if dlg.exec() == QtWidgets.QDialog.Accepted:
        vg_export.swap_id_map_color(dlg.source_color(), dlg.target_color())


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


### AUTO THUMBNAIL ###

def _on_project_saved(e):
    if vg_settings.load_settings().get("auto_thumbnail", False):
        vg_export.save_viewport_thumbnail(silent=True)


def _on_project_opened(e):
    if vg_settings.load_settings().get("auto_thumbnail", False):
        QTimer.singleShot(1000, lambda: vg_export.save_viewport_thumbnail(silent=True))


def _on_project_created(e):
    if vg_settings.load_settings().get("auto_thumbnail", False):
        QTimer.singleShot(1000, lambda: vg_export.save_viewport_thumbnail(silent=True))


def _connect_auto_thumbnail_events():
    event.DISPATCHER.connect_strong(event.ProjectSaved,   _on_project_saved)
    event.DISPATCHER.connect_strong(event.ProjectOpened,  _on_project_opened)
    event.DISPATCHER.connect_strong(event.ProjectCreated, _on_project_created)


def _disconnect_auto_thumbnail_events():
    for ev, cb in [
        (event.ProjectSaved,   _on_project_saved),
        (event.ProjectOpened,  _on_project_opened),
        (event.ProjectCreated, _on_project_created),
    ]:
        try:
            event.DISPATCHER.disconnect(ev, cb)
        except Exception:
            pass


def toggle_auto_thumbnail():
    """Toggle the auto thumbnail setting and update the menu action check state."""
    settings = vg_settings.load_settings()
    new_state = not settings.get("auto_thumbnail", False)
    settings["auto_thumbnail"] = new_state
    vg_settings.save_settings(settings)
    if _auto_thumbnail_action is not None:
        _auto_thumbnail_action.setChecked(new_state)


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
    "new_paint_layer":          new_paint_layer,
    "new_fill_layer_base":      partial(_new_fill_layer, active_channels=["BaseColor"]),
    "new_fill_layer_height":    partial(_new_fill_layer, active_channels=["Height"]),
    "new_fill_layer_all":       _new_fill_layer,
    "new_fill_layer_empty":     partial(_new_fill_layer, active_channels=[""]),
    "add_mask_popup":           add_mask_popup,
    "create_id_map_from_group": create_id_map_from_group,
    "id_color_swap":            id_color_swap,
    "palette_extractor":        open_palette_panel,
    "create_ref_point_layer":   create_ref_point_layer,
    "launch_quick_bake":        launch_quick_bake,
    "launch_bake_all":          launch_bake_all,
    "collection_panel":         open_collections_panel,
    "save_viewport_thumbnail":  save_viewport_thumbnail,
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
    "create_id_map_from_group",
    "id_color_swap",
    "palette_extractor",
    None,
    "create_ref_point_layer",
    None,
    "launch_quick_bake",
    "launch_bake_all",
    None,
    "collection_panel",
    None,
    "save_viewport_thumbnail",
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

    vg_utilities_menu.addSeparator()
    global _auto_thumbnail_action
    _auto_thumbnail_action = QtGui.QAction("Auto Thumbnail on Save", vg_utilities_menu)
    _auto_thumbnail_action.setCheckable(True)
    _auto_thumbnail_action.setChecked(settings.get("auto_thumbnail", False))
    _auto_thumbnail_action.triggered.connect(toggle_auto_thumbnail)
    vg_utilities_menu.addAction(_auto_thumbnail_action)

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
    _connect_auto_thumbnail_events()
    settings = vg_settings.load_settings()
    if settings.get("collection_panel_open", False):
        QTimer.singleShot(500, open_collections_panel)
    if settings.get("palette_panel_open", False):
        QTimer.singleShot(500, open_palette_panel)
    logging.info("VG Menu Activated")
    QTimer.singleShot(8000, _run_startup_update_check)
    

def close_plugin():
    """Called when the plugin is stopped."""
    global _mask_popup_menu, _collection_panel, _collection_dock, _palette_panel, _palette_dock, _auto_thumbnail_action
    _disconnect_auto_thumbnail_events()
    _auto_thumbnail_action = None

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
            _palette_panel.cleanup()
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
            _palette_panel.cleanup()
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

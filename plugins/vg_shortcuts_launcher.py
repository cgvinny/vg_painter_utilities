###############################################################################
# 
# This script will create a series of shortcuts for Substance 3D Painter
# ___________________
# Copyright 2024 Vincent GAULT - Adobe
# All Rights Reserved.
#
###############################################################################

"""
This module is used to enable different shortcuts within Substance Painter.
Here is the list of the existing shortcuts:

`Ctrl + P`: New Paint layer

`Ctrl + F`: New Fill layer with Base Color activated

`Ctrl + Alt + F`: New Fill layer with Height activated

`Ctrl + Shift + F`: New Fill layer, all channels activated

`Ctrl + M`: Add black mask to selected layer

`Ctrl + Shift + M`: Add black mask with AO Generator

`Ctrl + Alt + M`: Add black mask with Curvature Generator

`Ctrl + Shift + G`: Generate Layer from Stack visible content
"""

__author__ = "Vincent GAULT - Adobe"

# Modules import
from PySide2 import QtWidgets, QtGui, QtCore
import importlib

from substance_painter import ui, logging
from vg_pt_utils import vg_export, vg_layerstack

plugin_shortcuts_widgets = []
"""Keeps track of added UI elements for cleanup"""

# Create and connect a shortcut
def create_shortcut(key_sequence, function):
    """Creates a shortcut and connects it to a function."""
    shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(key_sequence), ui.get_main_window())
    plugin_shortcuts_widgets.append(shortcut)
    shortcut.activated.connect(function)
    return shortcut

######## FILL LAYER SHORTCUTS (F) ########

def on_ctrl_plus_f_shortcut_activated():
    """Creates a new fill layer with the Base Color channel activated."""
    try:
        stack_manager = vg_layerstack.VG_StackManager()
        stack_manager.add_layer('fill', active_channels=["BaseColor"])
    except Exception as e:
        logging.error(f"Failed to add fill layer with Base Color: {e}")

def on_ctrl_plus_alt_plus_f_shortcut_activated():
    """Creates a new fill layer with the Height channel activated."""
    try:
        stack_manager = vg_layerstack.VG_StackManager()
        stack_manager.add_layer('fill', active_channels=["Height"])
    except Exception as e:
        logging.error(f"Failed to add fill layer with Height: {e}")

def on_ctrl_plus_shift_plus_f_shortcut_activated():
    """Creates a new fill layer with all channels activated."""
    try:
        stack_manager = vg_layerstack.VG_StackManager()
        stack_manager.add_layer('fill')
    except Exception as e:
        logging.error(f"Failed to add fill layer with all channels: {e}")

######## PAINT LAYER SHORTCUTS (P) ########

def on_ctrl_plus_p_shortcut_activated():
    """Creates a new paint layer."""
    try:
        stack_manager = vg_layerstack.VG_StackManager()
        stack_manager.add_layer('paint')
    except Exception as e:
        logging.error(f"Failed to add paint layer: {e}")

######## MASK SHORTCUTS (M) ########

def on_ctrl_plus_m_shortcut_activated():
    """Adds a black mask to the selected layer."""
    try:
        stack_manager = vg_layerstack.VG_StackManager()
        stack_manager.add_mask()
    except Exception as e:
        logging.error(f"Failed to add black mask: {e}")

def on_ctrl_plus_shift_plus_m_shortcut_activated():
    """Adds a black mask with AO Generator to the selected layer."""
    try:
        stack_manager = vg_layerstack.VG_StackManager()
        stack_manager.add_black_mask_with_ao_generator()
    except Exception as e:
        logging.error(f"Failed to add black mask with AO Generator: {e}")

def on_ctrl_plus_alt_plus_m_shortcut_activated():
    """Adds a black mask with Curvature Generator to the selected layer."""
    try:
        stack_manager = vg_layerstack.VG_StackManager()
        stack_manager.add_black_mask_with_curvature_generator()
    except Exception as e:
        logging.error(f"Failed to add black mask with Curvature Generator: {e}")

######## GENERATE LAYER SHORTCUT ########

def on_ctrl_plus_shift_plus_g_shortcut_activated():
    """Generates a layer from the visible content in the stack."""
    try:
        exporter_manager = vg_export.VG_ExportManager()
        exported_textures = exporter_manager.export_active_texture_set()
        exporter_manager.import_textures_to_layer(exported_textures)
    except Exception as e:
        logging.error(f"Failed to generate layer from visible content: {e}")

def define_shortcuts():
    """Defines the various keyboard shortcuts."""
    hidden_window = QtWidgets.QWidget()
    plugin_shortcuts_widgets.append(hidden_window)

    shortcuts = {
        QtCore.Qt.CTRL + QtCore.Qt.Key_F: on_ctrl_plus_f_shortcut_activated,
        QtCore.Qt.CTRL + QtCore.Qt.ALT + QtCore.Qt.Key_F: on_ctrl_plus_alt_plus_f_shortcut_activated,
        QtCore.Qt.CTRL + QtCore.Qt.SHIFT + QtCore.Qt.Key_F: on_ctrl_plus_shift_plus_f_shortcut_activated,
        QtCore.Qt.CTRL + QtCore.Qt.Key_P: on_ctrl_plus_p_shortcut_activated,
        QtCore.Qt.CTRL + QtCore.Qt.Key_M: on_ctrl_plus_m_shortcut_activated,
        QtCore.Qt.CTRL + QtCore.Qt.SHIFT + QtCore.Qt.Key_M: on_ctrl_plus_shift_plus_m_shortcut_activated,
        QtCore.Qt.CTRL + QtCore.Qt.ALT + QtCore.Qt.Key_M: on_ctrl_plus_alt_plus_m_shortcut_activated,
        QtCore.Qt.CTRL + QtCore.Qt.SHIFT + QtCore.Qt.Key_G: on_ctrl_plus_shift_plus_g_shortcut_activated,
    }

    for key_sequence, function in shortcuts.items():
        create_shortcut(key_sequence, function)

    ui.add_dock_widget(hidden_window)

def start_plugin():
    """This function is called when the plugin is started."""
    define_shortcuts()
    logging.info("Shortcut Launcher activated")
    logging.info("---")
    logging.info("Ctrl + P: New Paint layer")
    logging.info("---")
    logging.info("Ctrl + F: New Fill layer with Base Color activated")
    logging.info("Ctrl + Alt + F: New Fill layer with Height activated")
    logging.info("Ctrl + Shift + F: New Fill layer, all channels activated")
    logging.info("---")
    logging.info("Ctrl + M: Add black mask to selected layer")
    logging.info("Ctrl + Shift + M: Add black mask with AO Generator")
    logging.info("Ctrl + Alt + M: Add black mask with Curvature Generator")
    logging.info("---")
    logging.info("Ctrl + Shift + G: Generate layer from what's visible in Stack")

def close_plugin():
    """This function is called when the plugin is stopped."""
    for widget in plugin_shortcuts_widgets:
        if widget is not None:
            ui.delete_ui_element(widget)
    plugin_shortcuts_widgets.clear()
    logging.info("Shortcut Launcher deactivated")

def reload_plugin():
    """Reloads the plugin modules."""
    importlib.reload(vg_layerstack)
    importlib.reload(vg_export)

if __name__ == "__main__":
    importlib.reload(vg_layerstack)
    importlib.reload(vg_export)
    start_plugin()

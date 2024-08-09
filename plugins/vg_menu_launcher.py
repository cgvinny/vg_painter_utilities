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
from PySide2 import QtWidgets
import importlib
import os

from substance_painter import ui, logging
from vg_pt_utils import vg_export, vg_layerstack

plugin_menus_widgets = []
"""Keeps track of added UI elements for cleanup."""

######## FILL LAYER FUNCTIONS ########

def new_fill_layer_base():
    """Create a new fill layer with Base Color activated."""
    stack_manager = vg_layerstack.VG_StackManager()
    stack_manager.add_layer('fill', active_channels=["BaseColor"])

def new_fill_layer_height():
    """Create a new fill layer with Height channel activated."""
    stack_manager = vg_layerstack.VG_StackManager()
    stack_manager.add_layer('fill', active_channels=["Height"])

def new_fill_layer_all():
    """Create a new fill layer with all channels activated."""
    stack_manager = vg_layerstack.VG_StackManager()
    stack_manager.add_layer('fill')

######## PAINT LAYER FUNCTIONS ########    

def new_paint_layer():
    """Create a new paint layer."""
    stack_manager = vg_layerstack.VG_StackManager()
    stack_manager.add_layer('paint')

######## MASK FUNCTIONS ########

def add_mask():
    """Add a black mask to the selected layer."""
    stack_manager = vg_layerstack.VG_StackManager()
    stack_manager.add_mask()

def add_ao_mask():
    """Add a black mask with AO Generator."""
    stack_manager = vg_layerstack.VG_StackManager()
    stack_manager.add_black_mask_with_ao_generator()

def add_curvature_mask():
    """Add a black mask with Curvature Generator."""
    stack_manager = vg_layerstack.VG_StackManager()
    stack_manager.add_black_mask_with_curvature_generator()

################ GENERATE CONTENT FROM STACK #######################    

def create_layer_from_stack():
    """Generate a layer from the visible content in the stack."""
    exporter_manager = vg_export.VG_ExportManager()
    exported_textures = exporter_manager.export_active_texture_set()
    exporter_manager.import_textures_to_layer(exported_textures)

def flatten_stack():
    """Flatten the stack by exporting and importing textures."""
    exporter_manager = vg_export.VG_ExportManager()
    stack_manager = vg_layerstack.VG_StackManager()
    exported_textures = exporter_manager.export_active_texture_set()
    stack_manager.delete_stack_content()
    exporter_manager.import_textures_to_layer(exported_textures)

########################################################### 

def create_menu():    
    """Create and populate the menu with actions."""
    # Get the main window
    main_window = ui.get_main_window()    

    # Create a new menu
    vg_utilities_menu = QtWidgets.QMenu("VG Utilities", main_window)
    ui.add_menu(vg_utilities_menu)
    plugin_menus_widgets.append(vg_utilities_menu)

    # Create actions
    actions = {
        "New Paint Layer (Ctrl+P)": new_paint_layer,
        "New Fill Layer with Base Color (Ctrl+F)": new_fill_layer_base,
        "New Fill Layer with Height (Ctrl+Alt+F)": new_fill_layer_height,
        "New Fill Layer with All Channels (Ctrl+Shift+F)": new_fill_layer_all,
        "Add Mask to Selected Layer (Ctrl+M)": add_mask,
        "Add AO Generator Mask (Ctrl+Shift+M)": add_ao_mask,
        "Add Curvature Generator Mask (Ctrl+Alt+M)": add_curvature_mask,
        "Create New Layer from Visible Stack (Ctrl+Shift+G)": create_layer_from_stack,
        "Flatten Stack": flatten_stack,
    }

    for text, func in actions.items():
        action = QtWidgets.QAction(text, vg_utilities_menu)
        action.triggered.connect(func)
        vg_utilities_menu.addAction(action)

def start_plugin():
    """Called when the plugin is started."""
    create_menu()
    logging.info("VG Menu Activated") 
    

def close_plugin():
    """Called when the plugin is stopped."""
    # Remove all added widgets from the UI.
    for widget in plugin_menus_widgets:
        ui.delete_ui_element(widget)
    plugin_menus_widgets.clear()
    logging.info("VG Menu deactivated")  

def reload_plugin():
    """Reload plugin modules."""
    importlib.reload(vg_layerstack)
    importlib.reload(vg_export)

if __name__ == "__main__":
    importlib.reload(vg_layerstack)
    importlib.reload(vg_export)
    start_plugin()

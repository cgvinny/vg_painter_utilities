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

from substance_painter import ui, logging, export
from vg_pt_utils import vg_baking, vg_export, vg_layerstack, vg_project_info

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

def add_mask_with_fill_effect():
    """Add a mask with a fill effect."""
    stack_manager = vg_layerstack.VG_StackManager()
    stack_manager.add_mask_with_fill()




################ GENERATE CONTENT FROM STACK #######################    

def create_layer_from_stack():
    """Generate a layer from the visible content in the stack."""
    vg_export.create_layer_from_stack()
    
    

def flatten_stack():
    """Flatten the stack by exporting and importing textures."""    
    vg_export.flatten_stack()
    




############## CREATE REFERENCE POINT LAYER ####################### 

def create_ref_point_layer():
    """Create a reference point layer"""
    stack_manager = vg_layerstack.VG_StackManager()
    stack_manager.generate_ref_point_layer()






########################### QUICK BAKE ########################### 

def launch_quick_bake():
    """Quickly bake mesh maps of the current texture set"""
    baker_manager = vg_baking.VG_BakerManager()
    baker_manager.quick_bake()
    
    
#################################################################



from PySide2.QtGui import QKeySequence

def create_menu():    
    """Create and populate the menu with actions."""
    # Get the main window
    main_window = ui.get_main_window()    

    # Create a new menu
    vg_utilities_menu = QtWidgets.QMenu("VG Utilities", main_window)
    ui.add_menu(vg_utilities_menu)
    plugin_menus_widgets.append(vg_utilities_menu)

    # Define actions, shortcuts, and separators
    actions_with_separators = [
        ("New Paint Layer", new_paint_layer, "Ctrl+P"),
        None,  # Separator
        ("New Fill Layer with Base Color", new_fill_layer_base, "Ctrl+F"),
        ("New Fill Layer with Height", new_fill_layer_height, "Ctrl+Alt+F"),
        ("New Fill Layer with All Channels", new_fill_layer_all, "Ctrl+Shift+F"),
        None,  # Separator
        ("Add Mask to Selected Layer", add_mask, "Ctrl+M"),
        ("Add Mask with Fill Effect", add_mask_with_fill_effect, "Shift+M"),
        ("Add Mask with AO Generator", add_ao_mask, "Ctrl+Shift+M"),
        ("Add Mask with Curvature Generator", add_curvature_mask, "Ctrl+Alt+M"),
        None,  # Separator
        ("Create New Layer from Visible Stack", create_layer_from_stack, "Ctrl+Shift+G"),
        ("Flatten Stack", flatten_stack, None),
        None,  # Separator
        ("Create Reference Point Layer", create_ref_point_layer, "Ctrl+R"),
        None,  # Separator
        #("Settings", open_settings_window, None)  # Settings button,
        ("quick bake", launch_quick_bake, "Ctrl+B"),
    ]

    # Add actions and separators to the menu
    for item in actions_with_separators:
        if item is None:
            vg_utilities_menu.addSeparator()
        else:
            text, func, shortcut = item
            action = QtWidgets.QAction(text, vg_utilities_menu)
            action.triggered.connect(func)
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))
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
    importlib.reload(vg_baking)
    importlib.reload(vg_project_info)

if __name__ == "__main__":
    importlib.reload(vg_layerstack)
    importlib.reload(vg_export)
    importlib.reload(vg_baking)
    importlib.reload(vg_project_info)

    start_plugin()

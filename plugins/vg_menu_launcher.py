###############################################################################

# This script will create a menu to host different tools for substance 3D Painter
# ___________________
# Copyright 2024 Vincent GAULT - Adobe
# All Rights Reserved.

###############################################################################
""""This module is used will create a menu to host different tools for Substance Painter.

 """


__author__ = "Vincent GAULT - Adobe"



# Modules import
from PySide2 import QtWidgets
import importlib
import os

from substance_painter import ui, logging
from vg_pt_utils import vg_export, vg_layerstack


plugin_menus_widgets = []
"""Keeps track of added ui elements for cleanup"""



######## FILL LAYER FUNCTIONS (F) ########


def new_fill_layer_base():
    stack_manager = vg_layerstack.VG_StackManager()
    stack_manager.add_layer('fill', active_channels=["BaseColor"])


def new_fill_layer_height():
    stack_manager = vg_layerstack.VG_StackManager()
    stack_manager.add_layer('fill', active_channels=["Height"])
    

def new_fill_layer_all():
    stack_manager = vg_layerstack.VG_StackManager()    
    stack_manager.add_layer('fill')
    
    
    
    

######## PAINT LAYER FUNCTIONS (P) ########    

def new_paint_layer():
    stack_manager = vg_layerstack.VG_StackManager()
    stack_manager.add_layer('paint')
    
    
    
    
######## MASK FUNCTIONS (M) ########

def add_mask():
    stack_manager = vg_layerstack.VG_StackManager()
    stack_manager.add_mask()
    
def add_ao_mask():
    stack_manager = vg_layerstack.VG_StackManager()
    stack_manager.add_black_mask_with_ao_generator()
    
def add_curvature_mask():
    stack_manager = vg_layerstack.VG_StackManager()
    stack_manager.add_black_mask_with_curvature_generator()

###########################################################    


def create_layer_from_stack():
    export_path = os.path.join(os.getenv('USERPROFILE'), 'Documents/Adobe/Adobe Substance 3D Painter/export')

    export_preset_name = "PBR Metallic Roughness"

    exporter = vg_export.VG_ExportManager(export_path, export_preset_name)
    #exporter.define_active_channels_export_info()
    exported_textures = exporter.export_active_texture_set()    
    exporter.import_textures_to_layer(exported_textures)
    
    

########################################################### 


def create_menu():    

    # Get the main window
    main_window = ui.get_main_window()    

    # Create a new menu
    vg_utilities_menu = QtWidgets.QMenu("VG Utilities", main_window)
    ui.add_menu(vg_utilities_menu)
    plugin_menus_widgets.append(vg_utilities_menu)

    # Create actions
    action_new_paint_layer = QtWidgets.QAction("New Paint Layer (Ctrl+P)", vg_utilities_menu)

    action_new_fill_layer_base = QtWidgets.QAction("New Fill Layer with Base Color    (Ctrl+F)", vg_utilities_menu)
    action_new_fill_layer_height = QtWidgets.QAction("New Fill Layer with Height    (Ctrl+Alt+F)", vg_utilities_menu)
    action_new_fill_layer_all = QtWidgets.QAction("New Fill Layer with All Activate Channels   (Ctrl+Shift+F)", vg_utilities_menu)

    action_add_mask = QtWidgets.QAction("Add Mask to Selected Layer  (Ctrl+M)", vg_utilities_menu)
    action_add_ao_mask = QtWidgets.QAction("Add AO Generator Mask   (Ctrl+Shift+M)", vg_utilities_menu)
    action_add_curvature_mask = QtWidgets.QAction("Add Curvature Generator Mask   (Ctrl+Alt+M)", vg_utilities_menu)

    action_create_layer_from_stack = QtWidgets.QAction("Create New Layer from Visible Stack   (Ctrl+Shift+G)", vg_utilities_menu)


    # Connect actions to functions
    action_new_paint_layer.triggered.connect(new_paint_layer)
    action_new_fill_layer_base.triggered.connect(new_fill_layer_base)
    action_new_fill_layer_height.triggered.connect(new_fill_layer_height)
    action_new_fill_layer_all.triggered.connect(new_fill_layer_all)
    action_add_mask.triggered.connect(add_mask)
    action_add_ao_mask.triggered.connect(add_ao_mask)
    action_add_curvature_mask.triggered.connect(add_curvature_mask)
    action_create_layer_from_stack.triggered.connect(create_layer_from_stack)


    # Add actions to the menu
    vg_utilities_menu.addAction(action_new_paint_layer)
    vg_utilities_menu.addSeparator()
    vg_utilities_menu.addAction(action_new_fill_layer_base)
    vg_utilities_menu.addAction(action_new_fill_layer_height)
    vg_utilities_menu.addAction(action_new_fill_layer_all)
    
    vg_utilities_menu.addAction(action_add_mask)
    vg_utilities_menu.addAction(action_add_ao_mask)
    vg_utilities_menu.addAction(action_add_curvature_mask)
    vg_utilities_menu.addSeparator()
    vg_utilities_menu.addAction(action_create_layer_from_stack)
    
    


def start_plugin():
    """This function is called when the plugin is started."""
    create_menu()
    logging.info("Vg Menu Activated") 
    
    
    
    


def close_plugin():
    """This function is called when the plugin is stopped."""
    
    # We need to remove all added widgets from the UI.
    for widget in plugin_menus_widgets:
        ui.delete_ui_element(widget)
        
    plugin_menus_widgets.clear()
    logging.info("Vg Menu deactivated")  


def reload_plugin():
    importlib.reload(vg_layerstack)
    importlib.reload(vg_export)
    logging.info("Vg Menu Reloaded") 

    

if __name__ == "__main__":
    importlib.reload(vg_layerstack)
    importlib.reload(vg_export)  
    start_plugin()
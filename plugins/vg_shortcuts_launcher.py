###############################################################################

# This script will create a series of shortcuts for substance 3D Painter
# ___________________
# Copyright 2024 Vincent GAULT - Adobe
# All Rights Reserved.

###############################################################################
""""This module is used to enable different shortcuts within Substance Painter.
here is the list of the existing shortcuts:

`Ctrl + P`: new Paint layer

---
`Ctrl + F`: new Fill layer with Base Color activated

`Ctrl + Alt + F`: new Fill layer with Height activated

`Ctrl + Shift + F`: new Fill layer, all channels activated

---
`Ctrl + M`: add black mask to selected layer

`Ctrl + Shift + M`: add black mask with AO Generator

`Ctrl + alt + M`: add black mask Curvature Generator """



__author__ = "Vincent GAULT - Adobe"



# Modules import
from PySide2 import QtWidgets, QtGui, QtCore
import importlib

from substance_painter import ui, logging
from vg_pt_utils import vg_layerstack


plugin_shortcuts_widgets = []
"""Keeps track of added ui elements for cleanup"""




######## FILL LAYER SHORTCUTS (F) ########

#Function to call for Ctrl + F shortcut
def on_ctrl_plus_f_shortcut_activated():
    stack_manager = vg_layerstack.CurrentStackManager()
    stack_manager.new_fill_with_bc()

#Function to call for  Ctrl + alt + F shortcut
def on_ctrl_plus_alt_plus_f_shortcut_activated():
    stack_manager = vg_layerstack.CurrentStackManager()
    stack_manager.new_fill_with_height()
    
#Function to call for  Ctrl + Shift + F shortcut
def on_ctrl_plus_shift_plus_f_shortcut_activated():
    stack_manager = vg_layerstack.CurrentStackManager()    
    stack_manager.new_fill_all_channels()
    
    
    

######## PAINT LAYER SHORTCUTS (P) ########    

#Function to call for  Ctrl + P shortcut
def on_ctrl_plus_p_shortcut_activated():
    stack_manager = vg_layerstack.CurrentStackManager()
    stack_manager.new_paint_layer()
    
    
    
    
######## MASK SHORTCUTS (M) ########

#Function to call for  Ctrl + M shortcut
def on_ctrl_plus_m_shortcut_activated():
    stack_manager = vg_layerstack.CurrentStackManager()
    stack_manager.add_mask()
    
#Function to call for  Ctrl + shift + M shortcut
def on_ctrl_plus_shift_plus_m_shortcut_activated():
    stack_manager = vg_layerstack.CurrentStackManager()
    stack_manager.add_black_mask_with_ao_generator()
    
#Function to call for  Ctrl + Alt + M shortcut
def on_ctrl_plus_alt_plus_m_shortcut_activated():
    stack_manager = vg_layerstack.CurrentStackManager()
    stack_manager.add_black_mask_with_curvature_generator()
    
    
    

def define_shortcuts():
    "This function is called to define the different shortcuts"    
    
    # Hidden Qt window creation
    hidden_window = QtWidgets.QWidget()
    plugin_shortcuts_widgets.append(hidden_window)    
    
    # Create a keyboard shortcut for "Ctrl + F" & connect it to the function
    ctrl_plus_f_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.CTRL + QtCore.Qt.Key_F), ui.get_main_window())
    plugin_shortcuts_widgets.append(ctrl_plus_f_shortcut)  
    ctrl_plus_f_shortcut.activated.connect(on_ctrl_plus_f_shortcut_activated)
    
    # Create a keyboard shortcut for "Ctrl + Alt + F" & connect it to the function
    ctrl_plus_alt_plus_f_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.CTRL + QtCore.Qt.ALT + QtCore.Qt.Key_F), ui.get_main_window())
    plugin_shortcuts_widgets.append(ctrl_plus_alt_plus_f_shortcut)  
    ctrl_plus_alt_plus_f_shortcut.activated.connect(on_ctrl_plus_alt_plus_f_shortcut_activated)
    
    # Create a keyboard shortcut for "Ctrl + Shift + F" & connect it to the function
    ctrl_plus_shift_plus_f_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.CTRL + QtCore.Qt.SHIFT + QtCore.Qt.Key_F), ui.get_main_window())
    plugin_shortcuts_widgets.append(ctrl_plus_shift_plus_f_shortcut)  
    ctrl_plus_shift_plus_f_shortcut.activated.connect(on_ctrl_plus_shift_plus_f_shortcut_activated)
    
    # Create a keyboard shortcut for "Ctrl + P" & connect it to the function
    ctrl_plus_p_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.CTRL + QtCore.Qt.Key_P), ui.get_main_window())
    plugin_shortcuts_widgets.append(ctrl_plus_p_shortcut)  
    ctrl_plus_p_shortcut.activated.connect(on_ctrl_plus_p_shortcut_activated)   
    
    # Create a keyboard shortcut for "Ctrl + M" & connect it to the function
    ctrl_plus_m_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.CTRL + QtCore.Qt.Key_M), ui.get_main_window())
    plugin_shortcuts_widgets.append(ctrl_plus_m_shortcut)  
    ctrl_plus_m_shortcut.activated.connect(on_ctrl_plus_m_shortcut_activated)
    
    # Create a keyboard shortcut for "Ctrl + shift + M" & connect it to the function
    ctrl_plus_shift_plus_m_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.CTRL + QtCore.Qt.SHIFT + QtCore.Qt.Key_M), ui.get_main_window())
    plugin_shortcuts_widgets.append(ctrl_plus_shift_plus_m_shortcut)  
    ctrl_plus_shift_plus_m_shortcut.activated.connect(on_ctrl_plus_shift_plus_m_shortcut_activated)  
    
    # Create a keyboard shortcut for "Ctrl + alt + M" & connect it to the function
    ctrl_plus_alt_plus_m_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.CTRL + QtCore.Qt.ALT + QtCore.Qt.Key_M), ui.get_main_window())
    plugin_shortcuts_widgets.append(ctrl_plus_alt_plus_m_shortcut)  
    ctrl_plus_alt_plus_m_shortcut.activated.connect(on_ctrl_plus_alt_plus_m_shortcut_activated)
    
    
    
    
    
    
    # Add hidden window to Pt UI
    ui.add_dock_widget(hidden_window)
    



def start_plugin():
    """This function is called when the plugin is started."""
    
   
    define_shortcuts()
    
    logging.info("Shortcut Launcher activated")
    logging.info("---")
    logging.info("Ctrl + P: new Paint layer")
    logging.info("---")
    logging.info("Ctrl + F: new Fill layer with Base Color activated")  
    logging.info("Ctrl + Alt + F: new Fill layer with Height activated")
    logging.info("Ctrl + Shift + F: new Fill layer, all channels activated")
    logging.info("---")
    logging.info("Ctrl + M: add black mask to selected layer")
    logging.info("Ctrl + Shift + M: add black mask with AO Generator")
    logging.info("Ctrl + alt + M: add mask Curvature Generator")
    


def close_plugin():
    """This function is called when the plugin is stopped."""
    
    # We need to remove all added widgets from the UI.
    for widget in plugin_shortcuts_widgets:
        ui.delete_ui_element(widget)
        
    plugin_shortcuts_widgets.clear()
    logging.info("Shortcut Launcher deactivated")  


def reload_plugin():
    importlib.reload(vg_layerstack)    

    

if __name__ == "__main__":
    importlib.reload(vg_layerstack)  
    start_plugin()
    
    
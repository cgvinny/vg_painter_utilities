##########################################################################
# 
# Copyright 2010-2024 Vincent GAULT - Adobe
# All Rights Reserved.
#
##########################################################################


"""
This module contains different utilities related to baking in
Substance 3d Painter.
"""
__author__ = "Vincent GAULT - Adobe"


#Modules import
import math
from substance_painter import baking, textureset, ui, event
from vg_pt_utils import vg_export

from substance_painter.baking import BakingParameters


class VG_BakerManager:
    """this class stores the different functions and modules in relation to the baking process in Substance 3D Painter"""
    
    #Initialization
    
    def __init__(self):
            """Class Initiaization"""
            
            self._current_baking_settings = None
            
            print("Event handler connected.")
            

    
    def on_baking_process_ended(self, e):
        print("Switching to paint view...")
        paint_mode = ui.UIMode(1)
        ui.switch_to_mode(paint_mode)
        print("Paint view activated.")
        event.DISPATCHER.disconnect(event.BakingProcessEnded,self.on_baking_process_ended)

    
    
    def quick_bake(self):
        
        
        # Get textureSet name
        export_manager = vg_export.VG_ExportManager()
        textureset_info = export_manager.get_textureset_info()
        textureset_name = textureset_info["Name"]
        current_textureset = textureset_info["Texture Set"]
        current_resolution = current_textureset.get_resolution()
        textureset_width = int(math.log2(current_resolution.width))
        textureset_height = int(math.log2(current_resolution.height))
        
        baking_params = BakingParameters.from_texture_set_name(textureset_name)
        common_params = baking_params.common()
        baking_params.set({common_params['OutputSize'] : (textureset_width,textureset_height),})

        # Build list of mesh maps to bake
        id_list = [1, 2, 3, 4, 5, 8, 9]
        map_usage_list = [textureset.MeshMapUsage(id) for id in id_list]
        
        #activate proper bakers
        baking_params.set_enabled_bakers(map_usage_list)

        

        
               
        current_textureset_info = vg_export.VG_ExportManager.get_textureset_info(self)
        current_textureset = current_textureset_info["Texture Set"]
        
        
        # Connect the event to the function to switch to the paint view
        event.DISPATCHER.connect_strong(event.BakingProcessEnded, self.on_baking_process_ended)
        
        # Start baking process
        baking.bake_async(current_textureset)

        print("Baking started...")
        

##########################################################################
# 
# Copyright 2010-2024 Vincent GAULT - Adobe
# All Rights Reserved.
#
##########################################################################

"""
This module contains different utilities related to baking in Substance 3D Painter.
"""
__author__ = "Vincent GAULT - Adobe"

# Modules import
import math
from substance_painter import baking, textureset, ui, event
from vg_pt_utils import vg_project_info
from substance_painter.baking import BakingParameters


class BakingParameterConfigurator:
    """
    Responsible for configuring baking parameters based on the texture set information.
    """

    def configure_baking_parameters(self, textureset_name, width, height):
        """
        Configure the baking parameters based on the texture set name and resolution.

        Args:
            textureset_name (str): The name of the texture set.
            width (int): The width of the texture set in log2 format.
            height (int): The height of the texture set in log2 format.

        Returns:
            BakingParameters: Configured baking parameters.
        """
        baking_params = BakingParameters.from_texture_set_name(textureset_name)
        common_params = baking_params.common()
        baking_params.set({common_params['OutputSize']: (width, height)})

        # Build list of mesh maps to bake
        id_list = [1, 2, 3, 4, 5, 8, 9]
        map_usage_list = [textureset.MeshMapUsage(id) for id in id_list]

        # Activate proper bakers
        baking_params.set_enabled_bakers(map_usage_list)

        return baking_params


class BakingProcessManager:
    """
    Responsible for managing the baking process and handling related events.
    """

    def __init__(self):
        self._current_baking_settings = None

    def on_baking_process_ended(self, e):
        """
        Event handler for when the baking process ends. Switches to paint view.
        """
        print("Switching to paint view...")
        paint_mode = ui.UIMode(1)
        ui.switch_to_mode(paint_mode)
        print("Paint view activated.")
        event.DISPATCHER.disconnect(event.BakingProcessEnded, self.on_baking_process_ended)

    def start_baking(self, current_texture_set):
        """
        Starts the baking process and connects the event handler.

        Args:
            current_texture_set (object): The current texture set to bake.
        """
        # Connect the event to the function to switch to the paint view
        event.DISPATCHER.connect_strong(event.BakingProcessEnded, self.on_baking_process_ended)

        # Start baking process
        baking.bake_async(current_texture_set)
        print("Baking started...")







##################### FUNCTIONS #####################

def quick_bake():
    """
    Perform a quick bake using the current texture set information and configured parameters.
    """
    # Fetch texture set information
    export_manager = vg_project_info.TextureSetInfo()
    textureset_info = export_manager.fetch_texture_set_info_from_stack()        
    textureset_name = textureset_info["Name"]
    current_texture_set = textureset_info["Texture Set"]
    
    # Calculate texture resolution in log2 format
    current_resolution = current_texture_set.get_resolution()
    width = int(math.log2(current_resolution.width))
    height = int(math.log2(current_resolution.height))
    
    # Configure baking parameters
    baking_param_configurator = BakingParameterConfigurator()
    baking_params = baking_param_configurator.configure_baking_parameters(textureset_name, width, height)

    # Start baking
    baking_process_manager = BakingProcessManager()
    baking_process_manager.start_baking(current_texture_set)


if __name__ == "__main__":
    quick_bake()

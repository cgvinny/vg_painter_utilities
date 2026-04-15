##########################################################################
#
# Copyright 2010-2024 Vincent GAULT - Adobe
# All Rights Reserved.
#
##########################################################################

"""
This module contains different utilities related to mesh maps baking in
Substance 3D Painter.
"""
__author__ = "Vincent GAULT - Adobe"

# Modules import
import math
from PySide6.QtCore import QTimer
from substance_painter import baking, textureset, ui, event
from vg_pt_utils import vg_project_info

# Mesh maps baked by quick_bake().
# Values correspond to textureset.MeshMapUsage enum members:
# Normal, WorldSpaceNormal, AO, Curvature, Height, ID, Opacity
QUICK_BAKE_MESH_MAPS = [1, 2, 3, 4, 5, 8, 9]


class BakingParameterConfigurator:
    """
    Configures baking parameters for a given texture set.
    """

    def configure_baking_parameters(self, textureset_name, width, height, mesh_maps_to_bake):
        """
        Build and return BakingParameters configured for the given texture set.

        Args:
            textureset_name (str): Name of the texture set.
            width (int): Output width in log2 format.
            height (int): Output height in log2 format.
            mesh_maps_to_bake (list[int]): MeshMapUsage values to enable.

        Returns:
            BakingParameters: Configured baking parameters.
        """
        baking_params = baking.BakingParameters.from_texture_set_name(textureset_name)
        common_params = baking_params.common()
        baking_params.set({common_params['OutputSize']: (width, height)})

        map_usage_list = [textureset.MeshMapUsage(id) for id in mesh_maps_to_bake]
        baking_params.set_enabled_bakers(map_usage_list)

        return baking_params


class BakingProcessManager:
    """
    Starts the baking process and handles the return to paint view on completion.
    """

    def _switch_to_paint_view(self):
        """Switch to paint view after baking completes."""
        ui.switch_to_mode(ui.UIMode(1))

    def _on_baking_ended(self, e):
        """
        Event handler for BakingProcessEnded.
        Defers the UI mode switch to the Qt main loop to avoid threading issues.
        """
        event.DISPATCHER.disconnect(event.BakingProcessEnded, self._on_baking_ended)
        QTimer.singleShot(0, self._switch_to_paint_view)

    def start_baking(self, current_texture_set):
        """
        Start the async baking process for the given texture set.

        Args:
            current_texture_set (TextureSet): The texture set to bake.
        """
        event.DISPATCHER.connect_strong(event.BakingProcessEnded, self._on_baking_ended)
        baking.bake_async(current_texture_set)


##################### FUNCTIONS #####################

def quick_bake():
    """
    Bake mesh maps for the active texture set using its current resolution.
    """
    ts_info = vg_project_info.TextureSetInfo().get_info()

    current_resolution = ts_info.texture_set.get_resolution()
    width = int(math.log2(current_resolution.width))
    height = int(math.log2(current_resolution.height))

    configurator = BakingParameterConfigurator()
    configurator.configure_baking_parameters(
        ts_info.name, width, height, QUICK_BAKE_MESH_MAPS
    )

    BakingProcessManager().start_baking(ts_info.texture_set)

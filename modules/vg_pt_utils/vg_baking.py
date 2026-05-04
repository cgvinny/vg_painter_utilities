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

# Mesh maps baked by quick_bake() and bake_all_texture_sets().
# Values correspond to textureset.MeshMapUsage enum members:
# Normal, WorldSpaceNormal, AO, Curvature, Height, ID, Opacity
QUICK_BAKE_MESH_MAPS = [1, 2, 3, 4, 5, 8, 9]


class BakingParameterConfigurator:
    """
    Configures baking parameters for a given texture set.
    """

    def configure_baking_parameters(self, texture_set, mesh_maps_to_bake):
        """
        Build and return BakingParameters configured for the given texture set.
        The output resolution is derived from the texture set's current resolution.

        Args:
            texture_set (TextureSet): The texture set to configure.
            mesh_maps_to_bake (list[int]): MeshMapUsage values to enable.

        Returns:
            BakingParameters: Configured baking parameters.
        """
        resolution = texture_set.get_resolution()
        width = int(math.log2(resolution.width))
        height = int(math.log2(resolution.height))

        baking_params = baking.BakingParameters.from_texture_set(texture_set)
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

    def _connect_event(self):
        event.DISPATCHER.connect_strong(event.BakingProcessEnded, self._on_baking_ended)

    def start_baking(self, current_texture_set):
        """
        Start the async baking process for a single texture set.

        Args:
            current_texture_set (TextureSet): The texture set to bake.
        """
        self._connect_event()
        ui.switch_to_mode(ui.UIMode(4))
        QTimer.singleShot(300, lambda: baking.bake_async(current_texture_set))

    def start_baking_all(self):
        """
        Start the async baking process for all enabled texture sets.
        Texture sets must be enabled via BakingParameters.set_textureset_enabled()
        before calling this method.
        """
        self._connect_event()
        ui.switch_to_mode(ui.UIMode(4))
        QTimer.singleShot(300, baking.bake_selected_textures_async)


##################### FUNCTIONS #####################

def quick_bake():
    """
    Bake mesh maps for the active texture set using its current resolution.
    Respects the baker selection currently configured in the Baking Room.
    """
    ts_info = vg_project_info.TextureSetInfo().get_info()
    baking_params = baking.BakingParameters.from_texture_set(ts_info.texture_set)
    enabled_maps = [m.value for m in baking_params.get_enabled_bakers()]
    BakingParameterConfigurator().configure_baking_parameters(
        ts_info.texture_set, enabled_maps
    )
    BakingProcessManager().start_baking(ts_info.texture_set)


def bake_all_texture_sets():
    """
    Bake mesh maps for all texture sets in the project, each at its own resolution.
    """
    configurator = BakingParameterConfigurator()
    for ts in textureset.all_texture_sets():
        params = configurator.configure_baking_parameters(ts, QUICK_BAKE_MESH_MAPS)
        params.set_textureset_enabled(True)
    BakingProcessManager().start_baking_all()

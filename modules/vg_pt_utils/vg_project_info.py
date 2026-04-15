##########################################################################
#
# Copyright 2010-2024 Vincent GAULT - Adobe
# All Rights Reserved.
#
##########################################################################

"""
This module contains classes to extract, gather, and organize relevant
information from Substance 3D Painter Texture Sets.
"""
__author__ = "Vincent GAULT - Adobe"

# Modules import
from typing import NamedTuple
from substance_painter import textureset, project, logging


class TextureSetData(NamedTuple):
    """Immutable snapshot of a texture set's metadata."""
    texture_set: object
    name: str
    channels: list
    uv_tiles_coordinates: list


class TextureSetInfo:
    """
    Gathers and exposes information about a specified texture set
    in Substance 3D Painter. If no stack is provided, the currently
    active texture set stack is used.
    """

    def __init__(self, target_stack=None):
        if not project.is_open():
            logging.error("TextureSetInfo: no project is open.")
            self._current_stack = None
            self._current_texture_set = None
            return

        self._current_stack = target_stack or textureset.get_active_stack()
        self._current_texture_set = self._current_stack.material()

    def get_info(self):
        """
        Return a TextureSetData with the texture set's name, channels,
        and UV tile coordinates.
        """
        uv_tiles = [
            [tile.u, tile.v]
            for tile in self._current_texture_set.all_uv_tiles()
        ]
        return TextureSetData(
            texture_set=self._current_texture_set,
            name=self._current_texture_set.name,
            channels=self._current_stack.all_channels(),
            uv_tiles_coordinates=uv_tiles,
        )

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
from substance_painter import textureset

# Classes definitions
class TextureSetInfo:
    """
    A class to gather and manage information about a specified texture set 
    in Substance 3D Painter. If no texture set is provided, the currently 
    active texture set will be used.
    """
    
    def __init__(self, target_stack=None):
        """
        Initialize the TextureSetInfo class.

        Parameters:
        target_stack (object): The target texture set stack. If None, 
                               the active texture set stack will be used.
        """
        if target_stack is None:
            self.current_stack = textureset.get_active_stack()
        else:
            self.current_stack = target_stack
        
        # Retrieve the material (texture set) from the stack
        self.current_texture_set = self.current_stack.material()

    def get_texture_set_object(self):
        """
        Retrieve the texture set object.

        Returns:
        object: The texture set object associated with the current stack.
        """
        return self.current_texture_set

    def get_texture_set_name(self):
        """
        Get the name of the texture set.

        Returns:
        str: The name of the texture set.
        """
        textureset_name = str(self.current_stack.material())  # Texture Set Name
        return textureset_name

    def generate_uv_tiles_coord_list(self):
        """
        Generate a list of UV tile coordinates for the current texture set.

        Returns:
        list: A list of [u, v] coordinates for each UV tile in the texture set.
        """
        uv_tiles_list = self.current_texture_set.all_uv_tiles()
        uv_tiles_coordinates_list = [[tile.u, tile.v] for tile in uv_tiles_list]
        return uv_tiles_coordinates_list

    def fetch_texture_set_info_from_stack(self):
        """
        Fetch and organize relevant information about the texture set, including 
        its name, channels, and UV tile coordinates.

        Returns:
        dict: A dictionary containing texture set information:
              - "Texture Set": The texture set object.
              - "Name": The name of the texture set.
              - "Channels": All channels present in the texture set.
              - "UV Tiles coordinates": A list of UV tile coordinates.
        """
        target_textureset = self.get_texture_set_object()
        texture_set_name = self.get_texture_set_name()
        texture_set_channels = self.current_stack.all_channels()         
        uv_tiles_coordinates_list = self.generate_uv_tiles_coord_list()

        # Generate and return the info dictionary
        textureset_info = {
            "Texture Set": target_textureset,
            "Name": texture_set_name,
            "Channels": texture_set_channels,
            "UV Tiles coordinates": uv_tiles_coordinates_list,
        }
        
        return textureset_info

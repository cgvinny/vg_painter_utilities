##########################################################################
# 
# Copyright 2010-2024 Vincent GAULT - Adobe
# All Rights Reserved.
#
##########################################################################


"""
This module contains different utilities related to the layer stack in
Substance 3d Painter.
"""


# Modules Import
from substance_painter import textureset, layerstack, project, resource, logging



class VG_StackManager:
    """
    The `VG_StackManager` class provides a set of utilities for managing layers within the active texture stack in Adobe Substance 3D Painter. It allows users to add various types of layers and set active channels, facilitating streamlined layer stack management.

    Features
    --------

    - **Initialization**: Automatically sets the current active texture stack when a project is open.
    - **Layer Management**: Supports adding fill and paint layers with customizable active channels.
    - **Channel Activation**: Allows specifying which channels should be active for newly created layers.
    - **Mask Management**: Provides functionality to add black masks to the currently selected layers.
    - **Error Handling**: Ensures that operations are performed only when an active stack is available, raising appropriate errors otherwise.

    Methods
    -------

    ### `__init__()`
    Initializes the `VG_StackManager` class and sets the current active texture stack if a project is open.

    ### `add_layer(layer_type, active_channels=None)`
    Adds a layer of the specified type to the current texture stack. The user can specify which channels should be active for the new layer.
    - `layer_type` (str): The type of layer to add (`'fill'` or `'paint'`).
    - `active_channels` (list, optional): A list of channel names to activate for the new layer. If not provided, all channels in the current stack will be activated.

    ### `set_active_channels(layer, channels)`
    Sets the active channels for a given layer.
    - `layer` (Layer): The layer for which to set active channels.
    - `channels` (list): A list of channel names to activate.

    ### `add_mask()`
    Adds a black mask to the currently selected layer.
    - Ensures that a mask is added only if a layer is selected.
    - Removes any existing mask before adding a new black mask.

    Example Usage
    -------------

    ```python
    manager = VG_StackManager()
    manager.add_layer('fill', active_channels=['BaseColor', 'Height'])
    manager.add_mask()
    """
    
    

    def __init__(self):
        """Class Initiaization"""
        
        self._current_stack = None
        if project.is_open():
            self._current_stack = textureset.get_active_stack()

    @property
    def current_stack(self):
        return self._current_stack

    @current_stack.setter
    def current_stack(self, value):
        self._current_stack = value
        
    
    
    
    def add_layer(self, layer_type, active_channels=None):
        """Add a layer of specified type to the current stack with optional active channels"""
        if self._current_stack is None:
            logging.error("No active stack found")
        
        else:
            

            # Insert at the top of the given textureset layer stack
            insert_position = layerstack.InsertPosition.from_textureset_stack(self._current_stack)
            new_layer = None
            
            if layer_type == 'fill':                
                new_layer = layerstack.insert_fill(insert_position)
                new_layer.set_name("New Fill layer")
                

            elif layer_type == 'paint':
                new_layer = layerstack.insert_paint(insert_position)
                new_layer.set_name("New Paint layer")
                
            else:
                logging.error("Invalid layer type")
                return
            
            # Set active channels if provided
            if active_channels:
                new_layer.active_channels = {getattr(textureset.ChannelType, channel) for channel in active_channels}
            else:
                active_channels = self._current_stack.all_channels()
                new_layer.active_channels = set(active_channels)

            # Select newly created layer
            layerstack.set_selected_nodes([new_layer])
            return new_layer

    
    
    
    # def set_active_channels(self, layer, channels):
    #     """Set active channels for a given layer"""
    #     layer.active_channels = {getattr(textureset.ChannelType, channel) for channel in channels}



    
    
    
    def add_mask(self, mask_bkg_color=None):
        """Adds a mask to the currently selected layer. 
        - If mask_bkg_color is specified, it applies the specified color (Black or White).
        - If mask_bkg_color is not specified and no mask is present, Black is chosen.
        - If mask_bkg_color is not specified and a mask is present, the existing mask is inverted."""
        
        color_map = {
            'Black': layerstack.MaskBackground.Black,  
            'White': layerstack.MaskBackground.White  
        }

        if mask_bkg_color and mask_bkg_color not in color_map:
            logging.error("Invalid mask color. Choose 'Black' or 'White'.")
            return

        # self._current_stack = textureset.get_active_stack()
        if self.current_stack:
            current_layer = layerstack.get_selected_nodes(self.current_stack)

            for selectedLayer in current_layer:
                if selectedLayer.has_mask():  
                    if mask_bkg_color:
                        # If a mask is present and a color is specified, remove the existing mask and add the specified color
                        selectedLayer.remove_mask()  
                        selectedLayer.add_mask(color_map[mask_bkg_color]) 
                    else:
                        # If no mask color is specified, invert the existing mask
                        current_mask_background = selectedLayer.get_mask_background()
                        new_mask_background = (layerstack.MaskBackground.White if current_mask_background == layerstack.MaskBackground.Black 
                                            else layerstack.MaskBackground.Black)
                        selectedLayer.remove_mask()
                        selectedLayer.add_mask(new_mask_background)
                else:
                    mask_to_add = color_map.get(mask_bkg_color, layerstack.MaskBackground.Black)
                    selectedLayer.add_mask(mask_to_add)

                

    def add_black_mask_with_ao_generator(self):
        """Adds a black mask with an ambient occlusion generator to the currently selected layer."""
        self.add_mask('Black')
        if self.current_stack:
            current_layer = layerstack.get_selected_nodes(self.current_stack)
            generator_resource = resource.search("s:starterassets u:generator n:Ambient Occlusion")[0]
            
            for selectedLayer in current_layer:
                insertion_position = layerstack.InsertPosition.inside_node(selectedLayer, layerstack.NodeStack.Mask)
                layerstack.insert_generator_effect(insertion_position, generator_resource.identifier())
                

    def add_black_mask_with_curvature_generator(self):
        """Adds a black mask with a curvature generator to the currently selected layer."""
        self.add_mask('Black')
        if self.current_stack:
            current_layer = layerstack.get_selected_nodes(self.current_stack)
            generator_resource = resource.search("s:starterassets u:generator n:Curvature")[0]
            
            for selectedLayer in current_layer:
                insertion_position = layerstack.InsertPosition.inside_node(selectedLayer, layerstack.NodeStack.Mask)
                layerstack.insert_generator_effect(insertion_position, generator_resource.identifier())
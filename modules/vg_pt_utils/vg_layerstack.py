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
__author__ = "Vincent GAULT - Adobe"



# Modules Import
from substance_painter import textureset, layerstack, project, resource, logging, colormanagement


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
    
    
    # Class initialization
    def __init__(self):
        """Class Initiaization"""
        
        self._current_stack = None
        self._layer_selection = None
        self._stack_layers = None
        self._stack_layers_count = None
        
        if project.is_open():
            self._current_stack = textureset.get_active_stack()
            self._layer_selection = layerstack.get_selected_nodes(self._current_stack)            

    @property
    def current_stack(self):
        return self._current_stack    

    @current_stack.setter
    def current_stack(self, value):
        self._current_stack = value
        
        
    @property
    def layer_selection(self):
        return self._layer_selection
   
    @layer_selection.setter
    def layer_selection(self, value):
        self._layer_selection = value
        
    
    @property
    def stack_layers(self):
        if self._stack_layers is None:
            self._stack_layers = layerstack.get_root_layer_nodes(self._current_stack)
        return self._stack_layers
    
    @property
    def stack_layers_count(self):
        if self._stack_layers_count is None:
            self._stack_layers_count = len(self.stack_layers)
        return self._stack_layers_count
    
    
    #################################""
    
    #Class Functions
    
    def refresh_layer_selection(self):
        self.layer_selection = layerstack.get_selected_nodes(self.current_stack)    
        
        
    
    #General function to simplfy layer creation
    def add_layer(self, layer_type, active_channels=None, layer_position="Above"):
        """Add a layer of specified type to the current stack with optional active channels"""
        
        if layer_position not in ["Above", "On Top"]:
            logging.error("layer_position parameter must be 'Above' or 'On Top'")
            return None        
        
        current_layer_count = self._stack_layers_count
                  
        
        if self._current_stack is None:
            logging.error("No active stack found")
            return None
        
        else:
            insert_position = None
            selected_layer = layerstack.get_selected_nodes(self._current_stack)
            
            if current_layer_count == 0:
                # Insert at the top of the given textureset layer stack
                insert_position = layerstack.InsertPosition.from_textureset_stack(self._current_stack)
                
            elif layer_position == "Above":
                # Insert a layer above new_layer                
                insert_position = layerstack.InsertPosition.above_node(selected_layer[0])
                
            elif layer_position == "On Top":
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
            
            return new_layer if new_layer else None
 
    
    #General function to create mask
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
            
            insertion_positions = [
                layerstack.InsertPosition.inside_node(layer, layerstack.NodeStack.Mask)
                for layer in current_layer
            ]
            for pos in insertion_positions:
                layerstack.insert_generator_effect(pos, generator_resource.identifier())
                

    def add_black_mask_with_curvature_generator(self):
        """Adds a black mask with a curvature generator to the currently selected layer."""
        self.add_mask('Black')
        if self.current_stack:
            current_layer = layerstack.get_selected_nodes(self.current_stack)
            generator_resource = resource.search("s:starterassets u:generator n:Curvature")[0]
            
            insertion_positions = [
                layerstack.InsertPosition.inside_node(layer, layerstack.NodeStack.Mask)
                for layer in current_layer
            ]
            for pos in insertion_positions:
                layerstack.insert_generator_effect(pos, generator_resource.identifier())
                
  
    # Add Mask with Fill layer
    def add_mask_with_fill(self):
        """Adds a black mask with a fill layer to the currently selected layer."""
        current_layer = layerstack.get_selected_nodes(self.current_stack)
        self.add_mask() # Add a mask
        
        
        inside_mask = layerstack.InsertPosition.inside_node(current_layer[0], layerstack.NodeStack.Mask) # defines position for the fill effect
        my_fill_effect_mask = layerstack.insert_fill(inside_mask)
        
        
        pure_white = colormanagement.Color(1.0, 1.0, 1.0)
        my_fill_effect_mask.set_source(channeltype=None, source=pure_white)


 
                
    
    #Delete Full Stack Content
    def delete_stack_content(self):
        current_layers = self.stack_layers
        for layer in current_layers:
            layerstack.delete_node(layer)
            
            
    
    # Generate Reference point layer
    def generate_ref_point_layer(self):
        
        base_name = "REF POINT LAYER"        
        all_nodes = layerstack.get_root_layer_nodes(self.current_stack)
        print(all_nodes)

       # Initialize the counter
        ref_point_count = 1

        # Loop through all nodes and count those that start with "REF POINT LAYER"
        for node in all_nodes:
            print(node.get_type())
            if node.get_name().startswith(base_name):
                ref_point_count += 1
            
            node_type = node.get_type()
            if node_type== layerstack.NodeType.GroupLayer:
                sublayers = node.sub_layers()
                for sublayer in sublayers:
                    if sublayer.get_name().startswith(base_name):
                        ref_point_count += 1
                    

        print(f"Number of layers starting with '{base_name}': {ref_point_count}")            
        ref_point_name = f"{base_name} ({ref_point_count})"    

        # Create the layer with a unique name
        ref_point_layer = self.add_layer("paint", layer_position="Above")
        ref_point_layer.set_name(ref_point_name)

        # Set all layer channels to "Passthrough" blending mode
        for new_layer_channel in ref_point_layer.active_channels:
            normal_blending = layerstack.BlendingMode(25)
            ref_point_layer.set_blending_mode(normal_blending, new_layer_channel)

        insert_position = layerstack.InsertPosition.inside_node(ref_point_layer, layerstack.NodeStack.Content)
        layerstack.insert_anchor_point_effect(insert_position, ref_point_name)


        
            
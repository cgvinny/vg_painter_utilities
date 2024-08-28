##########################################################################
# 
# Copyright 2010-2024 Vincent GAULT - Adobe
# All Rights Reserved.
#
##########################################################################

"""
This module contains different utilities related to the layer stack in
Substance 3D Painter.
"""
__author__ = "Vincent GAULT - Adobe"

# Modules Import
import string
from substance_painter import textureset, layerstack, project, resource, logging, colormanagement


class LayerManager:
    """
    The `LayerManager` class provides a set of utilities for managing layers within the active texture stack in Adobe Substance 3D Painter.
    """

    def __init__(self):
        """Class Initialization"""
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
    
    def refresh_layer_selection(self):
        self.layer_selection = layerstack.get_selected_nodes(self.current_stack)

    def add_layer(self, layer_type, layer_name ="New Layer", active_channels=None, layer_position="Above"):
        """Add a layer of specified type to the current stack with optional active channels"""
        
        if layer_position not in ["Above", "On Top"]:
            logging.error("layer_position parameter must be 'Above' or 'On Top'")
            return None
        
        current_layer_count = self._stack_layers_count
        if self._current_stack is None:
            logging.error("No active stack found")
            return None
        
        
        insert_position = None
        selected_layer = layerstack.get_selected_nodes(self._current_stack)
        
        if current_layer_count == 0:
            insert_position = layerstack.InsertPosition.from_textureset_stack(self._current_stack)
            
        elif layer_position == "Above":
            insert_position = layerstack.InsertPosition.above_node(selected_layer[0])
            
        elif layer_position == "On Top":
            insert_position = layerstack.InsertPosition.from_textureset_stack(self._current_stack)
        
        new_layer = None
        
        if layer_type == 'fill':
            new_layer = layerstack.insert_fill(insert_position)
           
        elif layer_type == 'paint':
            new_layer = layerstack.insert_paint(insert_position)
            
        else:
            logging.error("Invalid layer type")
            return
        
        if active_channels:
            new_layer.active_channels = {getattr(textureset.ChannelType, channel) for channel in active_channels}
        else:
            active_channels = self._current_stack.all_channels()
            new_layer.active_channels = set(active_channels)

        
        new_layer.set_name(layer_name)
        layerstack.set_selected_nodes([new_layer])
        
        return new_layer if new_layer else None

    
    def delete_stack_content(self):
        """Delete all layers in the current stack."""
        current_layers = self.stack_layers
        for layer in current_layers:
            layerstack.delete_node(layer)
            

    def generate_ref_point_layer(self):
        """Generate a reference point layer with unique naming and specific effects."""
        base_name = "REF POINT LAYER"        
        all_nodes = layerstack.get_root_layer_nodes(self.current_stack)

        ref_point_count = 1
        for node in all_nodes:
            if node.get_name().startswith(base_name):
                ref_point_count += 1
            if node.get_type() == layerstack.NodeType.GroupLayer:
                sublayers = node.sub_layers()
                for sublayer in sublayers:
                    if sublayer.get_name().startswith(base_name):
                        ref_point_count += 1

        # Fotmat the counter to be 2 digit numbers
        formatted_ref_point_count = f"_{str(ref_point_count).zfill(2)}"

        # build ref pint name
        ref_point_name = f"{base_name}{formatted_ref_point_count}"

        # Add new layer with proper name
        ref_point_layer = self.add_layer("paint", layer_position="Above")
        ref_point_layer.set_name(ref_point_name)


        for new_layer_channel in ref_point_layer.active_channels:
            normal_blending = layerstack.BlendingMode(25)
            ref_point_layer.set_blending_mode(normal_blending, new_layer_channel)

        insert_position = layerstack.InsertPosition.inside_node(ref_point_layer, layerstack.NodeStack.Content)
        layerstack.insert_anchor_point_effect(insert_position, ref_point_name)


class MaskManager:
    """
    The `MaskManager` class provides utilities for managing masks within the active texture stack in Adobe Substance 3D Painter.
    """

    def __init__(self, layer_manager):
        self.layer_manager = layer_manager

    def add_mask(self, mask_bkg_color=None):
        """Adds a mask to the currently selected layer with optional background color."""
        
        color_map = {
            'Black': layerstack.MaskBackground.Black,  
            'White': layerstack.MaskBackground.White  
        }

        if mask_bkg_color and mask_bkg_color not in color_map:
            logging.error("Invalid mask color. Choose 'Black' or 'White'.")
            return

        if self.layer_manager.current_stack:
            current_layer = layerstack.get_selected_nodes(self.layer_manager.current_stack)

            for selectedLayer in current_layer:
                if selectedLayer.has_mask():
                    if mask_bkg_color:
                        selectedLayer.remove_mask()
                        selectedLayer.add_mask(color_map[mask_bkg_color])
                    else:
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
        
        if self.layer_manager.current_stack:
            current_layer = layerstack.get_selected_nodes(self.layer_manager.current_stack)
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
        
        if self.layer_manager.current_stack:
            current_layer = layerstack.get_selected_nodes(self.layer_manager.current_stack)
            generator_resource = resource.search("s:starterassets u:generator n:Curvature")[0]
            
            insertion_positions = [
                layerstack.InsertPosition.inside_node(layer, layerstack.NodeStack.Mask)
                for layer in current_layer
            ]
            for pos in insertion_positions:
                layerstack.insert_generator_effect(pos, generator_resource.identifier())

    def add_mask_with_fill(self):
        """Adds a black mask with a fill layer to the currently selected layer."""
        current_layer = layerstack.get_selected_nodes(self.layer_manager.current_stack)
        self.add_mask()
        
        inside_mask = layerstack.InsertPosition.inside_node(current_layer[0], layerstack.NodeStack.Mask)
        my_fill_effect_mask = layerstack.insert_fill(inside_mask)
        
        pure_white = colormanagement.Color(1.0, 1.0, 1.0)
        my_fill_effect_mask.set_source(channeltype=None, source=pure_white)

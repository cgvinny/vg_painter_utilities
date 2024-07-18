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
from substance_painter import textureset, layerstack, project, resource



class CurrentStackManager:
    def __init__(self):
        """Class Initiaization"""
        
        self.current_stack = None
        if project.is_open():
            self.current_stack = textureset.get_active_stack()

    
    # Fill layers releasted modules
    def new_fill_with_bc(self):
        """Creates a fill layer with the base color activated"""
        
        if self.current_stack:
            insert_position = layerstack.InsertPosition.from_textureset_stack(self.current_stack)
            new_fill_layer = layerstack.insert_fill(insert_position)
            new_fill_layer.set_name("New Base color Fill layer")
            new_fill_layer.active_channels = {textureset.ChannelType.BaseColor}  # type: ignore
            layerstack.set_selected_nodes([new_fill_layer])  # type: ignore

    def new_fill_with_height(self):
        """Creates a fill layer with the height activated"""
        
        if self.current_stack:
            insert_position = layerstack.InsertPosition.from_textureset_stack(self.current_stack)
            new_fill_layer = layerstack.insert_fill(insert_position)
            new_fill_layer.set_name("New Height Fill layer")
            new_fill_layer.active_channels = {textureset.ChannelType.Height}  # type: ignore
            layerstack.set_selected_nodes([new_fill_layer])  # type: ignore

    def new_fill_all_channels(self):
        """Creates a fill layer with all channels activated"""
        
        if self.current_stack:
            insert_position = layerstack.InsertPosition.from_textureset_stack(self.current_stack)
            new_fill_layer = layerstack.insert_fill(insert_position)
            new_fill_layer.set_name("New Fill layer")
            activechannels = self.current_stack.all_channels()
            new_fill_layer.active_channels = set(activechannels)
            layerstack.set_selected_nodes([new_fill_layer])  # type: ignore

    
    
    #Paint Layer related modules
    def new_paint_layer(self):
        """Creates a new Paint layer"""
        
        if self.current_stack:
            insert_position = layerstack.InsertPosition.from_textureset_stack(self.current_stack)
            new_paint_layer = layerstack.insert_paint(insert_position)
            new_paint_layer.set_name("New Paint layer")
            activechannels = self.current_stack.all_channels()
            new_paint_layer.active_channels = set(activechannels)
            layerstack.set_selected_nodes([new_paint_layer])  # type: ignore

    
    
    
    #Mask related modules
    def add_mask(self):
        """Adds a black mask to the currently selected layer"""
        if self.current_stack:
            current_layer = layerstack.get_selected_nodes(self.current_stack)
            
            for selectedLayer in current_layer:
                if selectedLayer.has_mask():  # type: ignore
                    #selectedLayer.remove_mask()  # type: ignore
                    bkg_type = selectedLayer.get_mask_background() # type: ignore
                    if bkg_type == layerstack.MaskBackground.Black: # type: ignore
                        selectedLayer.remove_mask() # type: ignore
                        selectedLayer.add_mask(layerstack.MaskBackground.White)  # type: ignore
                    else:
                        selectedLayer.remove_mask() # type: ignore
                        selectedLayer.add_mask(layerstack.MaskBackground.Black)  # type: ignore
                else:
                    selectedLayer.add_mask(layerstack.MaskBackground.Black)  # type: ignore
            

    def add_black_mask_with_ao_generator(self):
        """Adds a black mask with an ambient occlusion generator to the currently selected layer"""
        if self.current_stack:
            current_layer = layerstack.get_selected_nodes(self.current_stack)
            generator_resource = resource.search("s:starterassets u:generator n:Ambient Occlusion")[0]
            
            for selectedLayer in current_layer:
                if not selectedLayer.has_mask():  # type: ignore
                    selectedLayer.add_mask(layerstack.MaskBackground.Black)  # type: ignore
                insertion_position = layerstack.InsertPosition.inside_node(selectedLayer, layerstack.NodeStack.Mask)
                layerstack.insert_generator_effect(insertion_position, generator_resource.identifier())

    def add_black_mask_with_curvature_generator(self):
        """Adds a black mask with a curvature generator to the currently selected layer"""
        if self.current_stack:
            current_layer = layerstack.get_selected_nodes(self.current_stack)
            generator_resource = resource.search("s:starterassets u:generator n:Curvature")[0]
            
            for selectedLayer in current_layer:
                if not selectedLayer.has_mask():  # type: ignore
                    selectedLayer.add_mask(layerstack.MaskBackground.Black)  # type: ignore
                insertion_position = layerstack.InsertPosition.inside_node(selectedLayer, layerstack.NodeStack.Mask)
                layerstack.insert_generator_effect(insertion_position, generator_resource.identifier())
                
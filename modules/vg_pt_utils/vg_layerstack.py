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
import re
from substance_painter import textureset, layerstack, project, resource, logging, colormanagement

# Blending mode constants
BLENDING_NORMAL = layerstack.BlendingMode(2)
BLENDING_NORMAL_REF_POINT = layerstack.BlendingMode(25)


class LayerManager:
    """
    Provides utilities for managing layers within the active texture stack
    in Adobe Substance 3D Painter.

    Note: LayerManager caches the stack and selection at init time.
    Create a new instance per operation — do not reuse across multiple actions.
    """

    def __init__(self):
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

    def add_layer(self, layer_type, layer_name="New Layer", active_channels=None, layer_position="Above"):
        """Add a layer of specified type to the current stack with optional active channels."""

        if layer_position not in ["Above", "On Top"]:
            logging.error("layer_position parameter must be 'Above' or 'On Top'")
            return None

        if self._current_stack is None:
            logging.error("No active stack found")
            return None

        selected_layer = layerstack.get_selected_nodes(self._current_stack)
        insert_position = None

        if self.stack_layers_count == 0:
            insert_position = layerstack.InsertPosition.from_textureset_stack(self._current_stack)

        elif layer_position == "Above":
            if not selected_layer:
                logging.error("No layer selected — cannot insert above.")
                return None
            insert_position = layerstack.InsertPosition.above_node(selected_layer[0])

        elif layer_position == "On Top":
            insert_position = layerstack.InsertPosition.from_textureset_stack(self._current_stack)

        if layer_type == 'fill':
            new_layer = layerstack.insert_fill(insert_position)
        elif layer_type == 'paint':
            new_layer = layerstack.insert_paint(insert_position)
        else:
            logging.error("Invalid layer type")
            return None

        if active_channels:
            if active_channels != [""]:
                new_layer.active_channels = {getattr(textureset.ChannelType, ch) for ch in active_channels}
        else:
            new_layer.active_channels = set(self._current_stack.all_channels())

        new_layer.set_name(layer_name)
        layerstack.set_selected_nodes([new_layer])

        return new_layer

    def delete_stack_content(self):
        """Delete all layers in the current stack."""
        for layer in self.stack_layers:
            layerstack.delete_node(layer)

    REF_POINT_BASE_NAME = "REF POINT LAYER"

    def get_next_ref_point_name(self, base_name=None):
        """
        Return the next available ref point layer name based on *base_name*
        (or the class default if omitted), using the highest existing suffix + 1.

        For example, if 'REF POINT LAYER_01' and 'REF POINT LAYER_06' exist,
        the next suggested name will be 'REF POINT LAYER_07'.
        """
        if base_name is None:
            base_name = self.REF_POINT_BASE_NAME
        pattern = re.compile(rf"^{re.escape(base_name)}_(\d+)$")
        all_nodes = layerstack.get_root_layer_nodes(self.current_stack)

        numbers = []
        for node in all_nodes:
            match = pattern.match(node.get_name())
            if match:
                numbers.append(int(match.group(1)))
            if node.get_type() == layerstack.NodeType.GroupLayer:
                for sublayer in node.sub_layers():
                    match = pattern.match(sublayer.get_name())
                    if match:
                        numbers.append(int(match.group(1)))

        next_number = max(numbers) + 1 if numbers else 1
        return f"{base_name}_{str(next_number).zfill(2)}"

    def generate_ref_point_layer(self, layer_name=None):
        """
        Generate a reference point layer with an anchor point effect.

        Args:
            layer_name (str | None): Name for the layer. If None, the next
                available default name is used (e.g. 'REF POINT LAYER_01').
        """
        if layer_name is None:
            layer_name = self.get_next_ref_point_name()

        ref_point_layer = self.add_layer("paint", layer_position="Above")
        ref_point_layer.set_name(layer_name)

        for channel in ref_point_layer.active_channels:
            ref_point_layer.set_blending_mode(BLENDING_NORMAL_REF_POINT, channel)

        insert_position = layerstack.InsertPosition.inside_node(ref_point_layer, layerstack.NodeStack.Content)
        layerstack.insert_anchor_point_effect(insert_position, layer_name)


class MaskManager:
    """
    Provides utilities for managing masks within the active texture stack
    in Adobe Substance 3D Painter.
    """

    def __init__(self, layer_manager):
        self.layer_manager = layer_manager

    def add_mask(self, mask_bkg_color=None):
        """
        Add a mask to the currently selected layer.

        If mask_bkg_color is None and a mask already exists, toggles it
        between Black and White. If mask_bkg_color is specified ('Black' or
        'White'), replaces any existing mask with the given background color.
        """
        color_map = {
            'Black': layerstack.MaskBackground.Black,
            'White': layerstack.MaskBackground.White,
        }

        if mask_bkg_color and mask_bkg_color not in color_map:
            logging.error("Invalid mask color. Choose 'Black' or 'White'.")
            return

        if not self.layer_manager.current_stack:
            return

        for selected_layer in layerstack.get_selected_nodes(self.layer_manager.current_stack):
            if selected_layer.has_mask():
                if mask_bkg_color:
                    selected_layer.remove_mask()
                    selected_layer.add_mask(color_map[mask_bkg_color])
                else:
                    current_bg = selected_layer.get_mask_background()
                    new_bg = (layerstack.MaskBackground.White
                              if current_bg == layerstack.MaskBackground.Black
                              else layerstack.MaskBackground.Black)
                    selected_layer.remove_mask()
                    selected_layer.add_mask(new_bg)
            else:
                selected_layer.add_mask(color_map.get(mask_bkg_color, layerstack.MaskBackground.Black))

    def _add_black_mask_with_generator(self, resource_query):
        self.add_mask('Black')
        if not self.layer_manager.current_stack:
            return
        generator_resource = resource.search(resource_query)[0]
        for layer in layerstack.get_selected_nodes(self.layer_manager.current_stack):
            pos = layerstack.InsertPosition.inside_node(layer, layerstack.NodeStack.Mask)
            layerstack.insert_generator_effect(pos, generator_resource.identifier())

    def add_black_mask_with_ao_generator(self):
        """Add a black mask with an Ambient Occlusion generator to the selected layer."""
        self._add_black_mask_with_generator("s:starterassets u:generator n:Ambient Occlusion")

    def add_black_mask_with_curvature_generator(self):
        """Add a black mask with a Curvature generator to the selected layer."""
        self._add_black_mask_with_generator("s:starterassets u:generator n:Curvature")

    def _mask_insert_position(self):
        """
        Add a mask to the selected layer and return an InsertPosition inside it.
        Helper shared by all 'add_mask_with_X' methods.
        """
        current_layer = layerstack.get_selected_nodes(self.layer_manager.current_stack)
        self.add_mask()
        return layerstack.InsertPosition.inside_node(current_layer[0], layerstack.NodeStack.Mask)

    def add_mask_with_fill(self):
        """Add a mask with a white fill effect to the selected layer."""
        pos = self._mask_insert_position()
        fill_effect = layerstack.insert_fill(pos)
        fill_effect.set_source(channeltype=None, source=colormanagement.Color(1.0, 1.0, 1.0))

    def add_mask_with_paint(self):
        """Add a mask with a paint layer to the selected layer."""
        layerstack.insert_paint(self._mask_insert_position())

    def add_mask_with_levels(self):
        """Add a mask with a Levels effect to the selected layer."""
        layerstack.insert_levels_effect(self._mask_insert_position())

    def add_mask_with_compare_mask(self):
        """Add a mask with a Compare Mask effect to the selected layer."""
        layerstack.insert_compare_mask_effect(self._mask_insert_position())

    def add_mask_with_color_selection(self):
        """Add a mask with a Color Selection effect to the selected layer."""
        layerstack.insert_color_selection_effect(self._mask_insert_position())

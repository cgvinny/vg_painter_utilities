##########################################################################
#
# Copyright 2010-2024 Vincent GAULT - Adobe
# All Rights Reserved.
#
##########################################################################

"""
This module contains utilities for exporting and re-importing textures
in Substance 3D Painter, used to flatten or snapshot the layer stack.
"""
__author__ = "Vincent GAULT - Adobe"

import os
from substance_painter import export, textureset, resource, layerstack
from vg_pt_utils import vg_layerstack, vg_project_info
from vg_pt_utils.vg_layerstack import BLENDING_NORMAL


def _extract_channel_type(texture_path):
    """
    Extract the ChannelType name from a texture file path.

    The file name is expected to end with _{channelName}.png.
    Maps 'ambientOcclusion' back to 'AO' to match ChannelType enum names.

    Returns:
        str | None: The channel type name, or None if the path is malformed.
    """
    last_underscore = texture_path.rfind("_")
    ext_index = texture_path.rfind(".png")
    if last_underscore == -1 or ext_index == -1:
        return None
    channel = texture_path[last_underscore + 1:ext_index].split(".")[0]
    return 'AO' if channel == 'ambientOcclusion' else channel


class TextureImporter:
    """Imports texture files into the project shelf."""

    def import_textures(self, textures_to_import):
        """
        Import textures from an export result into the project.

        Args:
            textures_to_import: Export result object with a .textures dict.

        Returns:
            dict: Imported texture resources keyed by file path.
        """
        imported_textures = {}
        for texture_list in textures_to_import.textures.values():
            for texture_path in texture_list:
                texture_resource = resource.import_session_resource(
                    texture_path, resource.Usage.TEXTURE
                )
                imported_textures[texture_path] = texture_resource
        return imported_textures


class LayerTextureAssigner:
    """Assigns imported textures to the correct channels of a fill layer."""

    def assign_textures_to_layer(self, new_layer, imported_textures):
        """
        Set each imported texture as the source for its corresponding channel.

        Args:
            new_layer: The fill layer to assign textures to.
            imported_textures (dict): Resources keyed by file path.
        """
        for texture_path, texture_resource in imported_textures.items():
            channel_name = _extract_channel_type(texture_path)
            if channel_name:
                channel_type = getattr(layerstack.ChannelType, channel_name)
                new_layer.set_source(channel_type, texture_resource.identifier())


class TextureAssignmentManager:
    """Orchestrates importing exported textures and assigning them to a fill layer."""

    def __init__(self):
        self._importer = TextureImporter()
        self._assigner = LayerTextureAssigner()

    def import_and_assign_textures(self, new_layer, textures_to_import):
        """
        Import textures from an export result, assign them to a fill layer,
        then delete the source PNG files from disk.

        Args:
            new_layer: The fill layer to populate.
            textures_to_import: Export result object.
        """
        imported_textures = self._importer.import_textures(textures_to_import)
        self._assigner.assign_textures_to_layer(new_layer, imported_textures)
        for texture_path in imported_textures:
            try:
                os.remove(texture_path)
            except OSError as e:
                print(f"Warning: could not delete texture file '{texture_path}': {e}")


class ExportConfigGenerator:
    """Builds the export configuration dict for the active texture set."""

    def __init__(self, export_path, preset_name="Current channels Export"):
        self.export_path = export_path
        self.preset_name = preset_name

    def generate_export_config(self):
        """Return a complete export configuration dict."""
        ts_info = vg_project_info.TextureSetInfo().get_info()

        udim_suffix = '.$udim' if ts_info.texture_set.has_uv_tiles() else ''
        channels_names = [
            'ambientOcclusion' if ch.name == 'AO' else ch.name
            for ch in ts_info.channels
        ]

        maps = []
        for channel_name in channels_names:
            maps.append({
                'fileName': f'$mesh_$textureSet_{channel_name}{udim_suffix}',
                'channels': [
                    {
                        "destChannel": c,
                        "srcChannel": c,
                        "srcMapType": "DocumentMap",
                        "srcMapName": channel_name,
                    }
                    for c in "RGBA"
                ],
                'parameters': {
                    'bitDepth': '8',
                    'dithering': False,
                    'fileFormat': 'png',
                },
            })

        return {
            "exportPath": self.export_path,
            "exportShaderParams": False,
            "defaultExportPreset": self.preset_name,
            "exportPresets": [{"name": self.preset_name, "maps": maps}],
            "exportList": [{"rootPath": ts_info.name}],
            "exportParameters": [
                {"parameters": {"dithering": True, "paddingAlgorithm": "infinite"}}
            ],
            "uvTiles": ts_info.uv_tiles_coordinates,
        }


class TextureExporter:
    """Executes a texture export using a given configuration dict."""

    def export_textures(self, export_config):
        """
        Run the export and return the result, or None on failure.

        Args:
            export_config (dict): Export configuration.

        Returns:
            ExportResult | None
        """
        try:
            export_result = export.export_project_textures(export_config)
            if export_result.status == export.ExportStatus.Error:
                print("Error during texture export:", export_result.message)
                return None
            return export_result
        except Exception as e:
            print(f"Error during texture export: {e}")
            return None


##### FUNCTIONS USING THE CLASSES #####

def _apply_textures_to_new_layer(stack_manager, exported_textures):
    """Create a Normal-blend fill layer on top of the stack and populate it with exported textures."""
    new_layer = stack_manager.add_layer("fill", layer_position="On Top", layer_name="Stack layer")
    for channel in new_layer.active_channels:
        new_layer.set_blending_mode(BLENDING_NORMAL, channel)
    TextureAssignmentManager().import_and_assign_textures(new_layer, exported_textures)


def create_layer_from_stack():
    """Export the visible stack content and import it as a new fill layer on top."""
    export_config = ExportConfigGenerator(export.get_default_export_path()).generate_export_config()
    exported_textures = TextureExporter().export_textures(export_config)
    if exported_textures:
        _apply_textures_to_new_layer(vg_layerstack.LayerManager(), exported_textures)


def create_layer_from_group():
    """
    Export the selected group's content in isolation and import it as a new
    fill layer placed just above the group.

    All other root-level layers are temporarily hidden during export, then
    restored — including on error. Layers inside the group are untouched.

    Note: if the group uses a non-Normal blending mode, the exported result
    reflects the group composited over a transparent background, not over
    the full stack.
    """
    current_stack = textureset.get_active_stack()
    selected = layerstack.get_selected_nodes(current_stack)

    if len(selected) != 1:
        print("VG: select exactly one group layer to use this function.")
        return
    target_group = selected[0]
    if target_group.get_type() != layerstack.NodeType.GroupLayer:
        print("VG: the selected layer is not a group.")
        return

    group_name = target_group.get_name()
    root_nodes = layerstack.get_root_layer_nodes(current_stack)
    saved_visibility = [(node, node.is_visible()) for node in root_nodes]

    success = False
    try:
        for node in root_nodes:
            node.set_visible(node == target_group)

        export_config = ExportConfigGenerator(export.get_default_export_path()).generate_export_config()
        exported_textures = TextureExporter().export_textures(export_config)

        if exported_textures:
            layerstack.set_selected_nodes([target_group])
            stack_manager = vg_layerstack.LayerManager()
            new_layer = stack_manager.add_layer(
                "fill", layer_position="Above", layer_name=f"{group_name} [Baked]"
            )
            for channel in new_layer.active_channels:
                new_layer.set_blending_mode(BLENDING_NORMAL, channel)
            TextureAssignmentManager().import_and_assign_textures(new_layer, exported_textures)
            success = True
    finally:
        for node, was_visible in saved_visibility:
            node.set_visible(was_visible)
        layerstack.set_selected_nodes(selected)

    if success:
        target_group.set_visible(False)


def create_id_map_from_group():
    """
    Export the selected group in isolation as an ID map and assign the result
    to the active texture set's ID mesh map slot.

    Only the BaseColor channel is exported (the user paints colour-coded zones
    in the group). All other root-level layers are temporarily hidden during
    export, then restored — including on error. The group itself is left intact
    and visible.
    """
    from PySide6 import QtWidgets
    from substance_painter import ui

    current_stack = textureset.get_active_stack()
    selected = layerstack.get_selected_nodes(current_stack)

    if len(selected) != 1 or selected[0].get_type() != layerstack.NodeType.GroupLayer:
        QtWidgets.QMessageBox.warning(
            ui.get_main_window(),
            "Create ID Map",
            "Select exactly one group layer to generate an ID map from.",
        )
        return

    target_group = selected[0]
    root_nodes = layerstack.get_root_layer_nodes(current_stack)
    saved_visibility = [(node, node.is_visible()) for node in root_nodes]

    try:
        for node in root_nodes:
            node.set_visible(node == target_group)

        ts_info = vg_project_info.TextureSetInfo().get_info()
        udim_suffix = '.$udim' if ts_info.texture_set.has_uv_tiles() else ''

        export_config = {
            "exportPath": export.get_default_export_path(),
            "exportShaderParams": False,
            "defaultExportPreset": "ID Map Export",
            "exportPresets": [{
                "name": "ID Map Export",
                "maps": [{
                    "fileName": f"$mesh_$textureSet_ID{udim_suffix}",
                    "channels": [
                        {"destChannel": c, "srcChannel": c,
                         "srcMapType": "DocumentMap", "srcMapName": "BaseColor"}
                        for c in "RGBA"
                    ],
                    "parameters": {"bitDepth": "8", "dithering": False, "fileFormat": "png"},
                }],
            }],
            "exportList": [{"rootPath": ts_info.name}],
            "exportParameters": [{"parameters": {"dithering": False, "paddingAlgorithm": "infinite"}}],
            "uvTiles": ts_info.uv_tiles_coordinates,
        }

        exported = TextureExporter().export_textures(export_config)
        if not exported:
            return

        texture_paths = [p for paths in exported.textures.values() for p in paths]
        if not texture_paths:
            return

        imported = resource.import_project_resource(texture_paths[0], resource.Usage.TEXTURE)
        ts_info.texture_set.set_mesh_map_resource(
            textureset.MeshMapUsage.ID, imported.identifier()
        )

    except Exception as e:
        QtWidgets.QMessageBox.critical(
            ui.get_main_window(), "Create ID Map", f"An error occurred:\n{e}"
        )
    finally:
        for node, was_visible in saved_visibility:
            node.set_visible(was_visible)
        layerstack.set_selected_nodes(selected)


def flatten_stack():
    """Flatten the stack by exporting its content, deleting all layers, and re-importing as a single fill layer."""
    export_config = ExportConfigGenerator(export.get_default_export_path()).generate_export_config()
    stack_manager = vg_layerstack.LayerManager()
    exported_textures = TextureExporter().export_textures(export_config)
    stack_manager.delete_stack_content()
    if exported_textures:
        _apply_textures_to_new_layer(stack_manager, exported_textures)

##########################################################################
#
# Copyright 2010-2024 Vincent GAULT - Adobe
# All Rights Reserved.
#
##########################################################################

# Modules Import
import os, time

from substance_painter import export, textureset, resource, layerstack
from vg_pt_utils import vg_layerstack, vg_project_info

class TextureImporter:
    """
    Responsible for importing textures from the file paths.
    """

    def import_textures(self, textures_to_import):
        """
        Import the textures from the specified paths.

        Args:
            textures_to_import (object): The exported textures to be imported.

        Returns:
            dict: A dictionary with the imported texture resources keyed by their respective paths.
        """
        imported_textures = {}
        texture_paths = []

        for texture_list_key in textures_to_import.textures.keys():
            current_texture_list = textures_to_import.textures[texture_list_key]

            for texture_path in current_texture_list:
                texture_paths.append(texture_path)  # Collect texture paths for cleanup later
                texture_resource = resource.import_project_resource(texture_path, resource.Usage.TEXTURE)
                imported_textures[texture_path] = texture_resource

        return imported_textures, texture_paths


class ChannelTypeExtractor:
    """
    Responsible for extracting the channel type from the texture file path.
    """

    def extract_channel_type(self, texture_path):
        """
        Extract the channel type from the texture file path.

        Args:
            texture_path (str): The file path of the texture.

        Returns:
            str: The extracted channel type.
        """
        last_underscore_index = texture_path.rfind("_")
        extension_index = texture_path.rfind(".png")
        if last_underscore_index != -1 and extension_index != -1:
            channel_type_string = texture_path[last_underscore_index + 1:extension_index]
            channel_type_string = channel_type_string.split(".")[0]
            if channel_type_string == 'ambientOcclusion':
                channel_type_string = 'AO'
            return channel_type_string
        return None


class LayerTextureAssigner:
    """
    Responsible for assigning imported textures to the correct channels in a fill layer.
    """

    def assign_textures_to_layer(self, new_layer, imported_textures):
        """
        Assign the imported textures to the correct channels in the new fill layer.

        Args:
            new_layer (object): The fill layer where the textures will be assigned.
            imported_textures (dict): A dictionary of imported texture resources keyed by their file paths.
        """
        extractor = ChannelTypeExtractor()

        for texture_path, texture_resource in imported_textures.items():
            channel_type_string = extractor.extract_channel_type(texture_path)

            if channel_type_string:
                print(f"Assigning texture to channel: {channel_type_string}")
                channel_type = getattr(layerstack.ChannelType, channel_type_string)
                new_layer.set_source(channel_type, texture_resource.identifier())

        print("Textures imported and assigned to the new fill layer.")
        


class ResourceCleaner:
    """
    Manages the cleanup of texture files after they are imported and assigned.
    """
    
    def delete_texture_files(self, texture_paths):
        """
        Deletes the texture files from disk after they have been imported.

        Args:
            texture_paths (list): List of texture file paths to delete.
        """
        for texture_path in texture_paths:
            try:
                os.remove(texture_path)
                print(f"Deleted file: {texture_path}")
            except Exception as e:
                print(f"Error deleting file {texture_path}: {e}")


class TextureAssignmentManager:
    """
    Manages the process of importing exported textures into a new fill layer and assigning them to the appropriate channels.
    """

    def __init__(self):
        self.texture_importer = TextureImporter()
        self.layer_assigner = LayerTextureAssigner()
        #self.resource_cleaner = ResourceCleaner()

    def import_and_assign_textures(self, new_layer, textures_to_import):
        """
        Import the exported textures into a new fill layer and assign them to the correct channels.

        Args:
            new_layer (object): The fill layer where the textures will be assigned.
            textures_to_import (object): The exported textures to be imported.
        """
        imported_textures, texture_paths = self.texture_importer.import_textures(textures_to_import)
        self.layer_assigner.assign_textures_to_layer(new_layer, imported_textures)
        #self.resource_cleaner.delete_texture_files(texture_paths)                                #do not uncomment


class ExportConfigGenerator:
    """
    Generates the export configuration for the active texture set.
    """

    def __init__(self, export_path, preset_name="Current channels Export"):
        self.export_path = export_path
        self.preset_name = preset_name

    def generate_current_channels_maps_export(self):
        current_stack = textureset.get_active_stack()
        texture_set_info_manager = vg_project_info.TextureSetInfo(current_stack)
        current_textureset_info = texture_set_info_manager.fetch_texture_set_info_from_stack()

        udim_suffix = ""
        current_texture_set = current_textureset_info["Texture Set"]
        if current_texture_set.has_uv_tiles():
            udim_suffix = '.$udim'

        raw_channels_list = current_textureset_info["Channels"]
        channels_names = [element.name for element in raw_channels_list]
        channels_names = [
            'ambientOcclusion' if element.name == 'AO' else element.name
            for element in raw_channels_list
        ]

        current_channels_info = []

        for channel_name in channels_names:
            channels_info = [
                {
                    "destChannel": channel,
                    "srcChannel": channel,
                    "srcMapType": "DocumentMap",
                    "srcMapName": channel_name
                } for channel in "RGBA"
            ]

            current_filename = f'$mesh_$textureSet_{channel_name}'
            current_filename = current_filename + udim_suffix

            current_channels_info.append({
                'fileName': current_filename,
                'channels': channels_info,
                'parameters': {
                    'bitDepth': '8',
                    'dithering': False,
                    'fileFormat': 'png'
                }
            })

        return current_channels_info

    def generate_export_config(self):
        current_channels_export_preset = {
            "name": self.preset_name,
            "maps": self.generate_current_channels_maps_export()
        }

        texture_set_info_manager = vg_project_info.TextureSetInfo()
        current_textureset_info = texture_set_info_manager.fetch_texture_set_info_from_stack()

        export_config = {
            "exportPath": self.export_path,
            "exportShaderParams": False,
            "defaultExportPreset": self.preset_name,
            "exportPresets": [current_channels_export_preset],
            "exportList": [{"rootPath": current_textureset_info["Name"]}],
            "exportParameters": [
                {"parameters": {"dithering": True, "paddingAlgorithm": "infinite"}}
            ],
            "uvTiles": current_textureset_info["UV Tiles coordinates"],
        }
        return export_config


class TextureExporter:
    """
    Handles the export of textures using a given export configuration.
    """

    def export_textures(self, export_config):
        try:
            export_result = export.export_project_textures(export_config)

            if export_result.status == export.ExportStatus.Error:
                print("Error during texture export:", export_result.message)
                return None
            else:
                print("Export successful!")
                return export_result

        except Exception as e:
            print(f"Error during texture export: {e}")
            return None


##### FUNCTIONS USING THE CLASSES #####

def create_layer_from_stack():
    """Generate a layer from the visible content in the stack."""
    
    # Generate the export configuration
    export_path = export.get_default_export_path()
    config_generator = ExportConfigGenerator(export_path)
    export_config = config_generator.generate_export_config()

    # Perform the export
    exporter = TextureExporter()
    exported_textures = exporter.export_textures(export_config)

    # Import the textures to a new layer
    if exported_textures:
        texture_manager = TextureAssignmentManager()
        current_stack_manager = vg_layerstack.LayerManager()

        new_layer = current_stack_manager.add_layer("fill", layer_position="On Top", layer_name="Stack layer")
        new_layer.active_channels = set(new_layer.active_channels)
        
        for new_layer_channel in new_layer.active_channels:
            normal_blending = layerstack.BlendingMode(2)
            new_layer.set_blending_mode(normal_blending, new_layer_channel)
        
        texture_manager.import_and_assign_textures(new_layer, exported_textures)


def flatten_stack():
    """Flatten the stack by exporting and importing textures."""
    
    export_path = export.get_default_export_path()
    config_generator = ExportConfigGenerator(export_path)

    # Generate the export configuration
    export_config = config_generator.generate_export_config()

    # Perform the export
    exporter = TextureExporter()
    stack_manager = vg_layerstack.LayerManager()
    exported_textures = exporter.export_textures(export_config)
    
    stack_manager.delete_stack_content() #delete before to reimport

    # Import the textures to a new layer
    if exported_textures:
        texture_manager = TextureAssignmentManager()
        new_layer = stack_manager.add_layer("fill", layer_position="On Top", layer_name="Stack layer")
        new_layer.active_channels = set(new_layer.active_channels)
        
        for new_layer_channel in new_layer.active_channels:
            normal_blending = layerstack.BlendingMode(2)
            new_layer.set_blending_mode(normal_blending, new_layer_channel)
        
        texture_manager.import_and_assign_textures(new_layer, exported_textures)
        

#####################################

if __name__ == "__main__":
    # Initialize the export configuration generator
    export_path = export.get_default_export_path()
    config_generator = ExportConfigGenerator(export_path)

    # Generate the export configuration
    export_config = config_generator.generate_export_config()

    # Perform the export
    exporter = TextureExporter()
    exported_textures = exporter.export_textures(export_config)

    # Import the textures to a new layer
    if exported_textures:
        texture_manager = TextureAssignmentManager()
        current_stack_manager = vg_layerstack.LayerManager()
        new_layer = current_stack_manager.add_layer("fill", layer_position="On Top", layer_name="Stack layer")
        new_layer.active_channels = set(new_layer.active_channels)
        
        for new_layer_channel in new_layer.active_channels:
            normal_blending = layerstack.BlendingMode(2)
            new_layer.set_blending_mode(normal_blending, new_layer_channel)
        
        texture_manager.import_and_assign_textures(new_layer, exported_textures)

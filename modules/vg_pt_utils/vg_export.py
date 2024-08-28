##########################################################################
#
# Copyright 2010-2024 Vincent GAULT - Adobe
# All Rights Reserved.
#
##########################################################################

# Modules Import
import os
from substance_painter import export, textureset, resource, layerstack
from vg_pt_utils import vg_layerstack, vg_project_info



class ExportConfigGenerator:
    """
    Generates the export configuration for the active texture set.
    """

    def __init__(self, export_path, preset_name="Current channels Export"):
        """
        Initialize the ExportConfigGenerator with the given export path and preset name.

        Args:
            export_path (str): The path where the textures will be exported.
            preset_name (str): The name of the export preset to be used.
        """
        self.export_path = export_path
        self.preset_name = preset_name

    def generate_current_channels_maps_export(self):
        """
        Generate the channel map export configurations for the active texture set.

        Returns:
            list: A list of dictionaries containing file name, channels, and parameters for each channel.
        """
        current_stack = textureset.get_active_stack()
        texture_set_info_manager = vg_project_info.TextureSetInfo(current_stack)
        current_textureset_info = texture_set_info_manager.fetch_texture_set_info_from_stack()

        raw_channels_list = current_textureset_info["Channels"]
        channels_names = [element.name for element in raw_channels_list]
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

            current_filename = f'$mesh_$textureSet_{channel_name}.$udim'
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
        """
        Generate the full export configuration for the active texture set.

        Returns:
            dict: A dictionary containing the full export configuration.
        """
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
        """
        Export the textures using the provided configuration.

        Args:
            export_config (dict): The configuration for exporting textures.

        Returns:
            object: The result of the export operation, or None if there was an error.
        """
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



class TextureAssigner:
    """
    Responsible for assigning imported textures to the correct channels in a fill layer.
    """

    def assign_textures_to_layer(self, new_layer, textures_to_import):
        """
        Assign the imported textures to the correct channels in the new fill layer.

        Args:
            new_layer (object): The fill layer where the textures will be assigned.
            textures_to_import (object): The exported textures to be imported.
        """
        for texture_list_key in textures_to_import.textures.keys():
            current_texture_list = textures_to_import.textures[texture_list_key]

            for texture_path in current_texture_list:
                texture_resource = resource.import_project_resource(texture_path, resource.Usage.TEXTURE)

                last_underscore_index = texture_path.rfind("_")
                extension_index = texture_path.rfind(".png")
                if last_underscore_index != -1 and extension_index != -1:
                    channel_type_string = texture_path[last_underscore_index + 1:extension_index]
                    channel_type_string = channel_type_string.split(".")[0]
                    channel_type = getattr(layerstack.ChannelType, channel_type_string)
                    new_layer.set_source(channel_type, texture_resource.identifier())

        print("Textures imported and assigned to the new fill layer.")


class TextureImporter:
    """
    Manages the process of importing exported textures into a new fill layer and assigning them to the appropriate channels.
    """

    def __init__(self):
        self.texture_assigner = TextureAssigner()

    def import_textures_to_layer(self, textures_to_import):
        """
        Import the exported textures into a new fill layer.

        Args:
            textures_to_import (object): The exported textures to be imported.
        """
        if not textures_to_import:
            print("No textures to import.")
            return

        
        current_stack_manager = vg_layerstack.LayerManager()
        new_layer = current_stack_manager.add_layer("fill", layer_position="On Top", layer_name="Stack layer")
        new_layer.active_channels = set(new_layer.active_channels)

        for new_layer_channel in new_layer.active_channels:
            normal_blending = layerstack.BlendingMode(2)
            new_layer.set_blending_mode(normal_blending, new_layer_channel)
        
        self.texture_assigner.assign_textures_to_layer(new_layer, textures_to_import)






##### FUNCTIONS USING THE CLASSES #####

def create_layer_from_stack():
    """Generate a layer from the visible content in the stack."""
    
    export_path = export.get_default_export_path()
    config_generator = ExportConfigGenerator(export_path)

    # Generate the export configuration
    export_config = config_generator.generate_export_config()

    # Perform the export
    exporter = TextureExporter()
    exported_textures = exporter.export_textures(export_config)

    # Import the textures to a new layer
    if exported_textures:
        importer = TextureImporter()
        importer.import_textures_to_layer(exported_textures)
        

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
    stack_manager.delete_stack_content()

    # Import the textures to a new layer
    if exported_textures:
        importer = TextureImporter()
        importer.import_textures_to_layer(exported_textures)

        
        
 

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
        importer = TextureImporter()
        importer.import_textures_to_layer(exported_textures)

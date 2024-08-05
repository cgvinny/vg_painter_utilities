##########################################################################
#
# Copyright 2010-2024 Vincent GAULT - Adobe
# All Rights Reserved.
#
##########################################################################


# Modules Import
import os
#import numpy
from re import split

#from numpy import append

from substance_painter import export, textureset, resource, layerstack
from vg_pt_utils import vg_layerstack


class VG_ExportManager:
    """
    A manager gathering different features related to export in Substance 3D Painter.

    Attributes:
    export_path (str): The path where textures will be exported.
    export_preset_name (str): The name of the export preset to use.

    Methods:
    get_export_preset():
        Obtains the URL of the specified export preset.

    get_textureset_info():
        Returns texture set information related to a stack (object, name, UV tiles coordinates) in a dictionary.

    export_active_texture_set():
        Exports the textures from the active texture set using the specified export preset.

    import_textures_to_layer(textures):
        Imports the exported textures into a new fill layer and assigns them to the appropriate channels.
    """

    def __init__(self, export_path, export_preset_name):
        self.export_path = export_path  # Define the export path
        self.export_preset_name = export_preset_name  # Define the export preset name

    def get_export_preset(self):
        # Obtain the URL of the export preset
        try:
            export_preset = resource.ResourceID(
                context="starter_assets", name=self.export_preset_name
            )
            return export_preset.url()

        except Exception as e:
            print(f"Error obtaining export preset: {e}")
            return None

    def get_textureset_info(self):
        """Returns Texture set related to a stack, and it's name into a dictionary
        If no argument, the current stack will be used to generate the information"""

        target_stack = textureset.get_active_stack()
        target_textureset = target_stack.material()  # textureSet Object
        texture_set_name = str(target_stack.material())  # textureSet Name
        texture_set_channels = target_stack.all_channels()

        # Generate UV tiles coordonates list
        uv_tiles_list = target_textureset.all_uv_tiles()
        uv_tiles_coordinates_list = []
        for tile in uv_tiles_list:
            coordinates = [tile.u, tile.v]
            uv_tiles_coordinates_list.append(coordinates)

        # Generate info dictionary
        textureset_info = {
            "Texture Set": target_textureset,
            "Name": texture_set_name,
            "UV Tiles coordinates": uv_tiles_coordinates_list,
            "Channels": texture_set_channels,
        }

        return textureset_info

   
    def generate_current_channels_maps_export(self):
    # Get Active TextureSet info:
        current_textureset_info = self.get_textureset_info()
        raw_channels_list = current_textureset_info["Channels"]
        channels_names = []
        current_channels_info = []

        for element in raw_channels_list:
            channels_names.append(element.name)

        for channel_name in channels_names:
            channels_info = []
            for channel in "RGBA":
                channels_info.append({
                    "destChannel": channel,
                    "srcChannel": channel,
                    "srcMapType": "DocumentMap",
                    "srcMapName": channel_name
                })
            current_filename = '$mesh_$textureSet_' + channel_name + ".$udim"
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
        #export_preset_ref = self.get_export_preset()
        export_preset_name = "Current channels Export"
        
        current_channels_export_preset = {
            "name": export_preset_name,
            "maps": self.generate_current_channels_maps_export()
        }
                
        # Get Active TextureSet info:
        current_textureset_info = self.get_textureset_info()
        
        # Configure the export settings
        export_config = {
            "exportPath": self.export_path,
            "exportShaderParams": False,
            "defaultExportPreset": export_preset_name,
            "exportPresets":[current_channels_export_preset],
            "exportList": [{"rootPath": current_textureset_info["Name"]}],
            "exportParameters": [
                {"parameters": {"dithering": True, "paddingAlgorithm": "infinite"}}
            ],
            "uvTiles": current_textureset_info["UV Tiles coordinates"],
        }
        return export_config
    
    
    def export_active_texture_set(self):
        
        # Configure the export settings
        export_config = self.generate_export_config()       

        try:
            # Perform the export
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

    def import_textures_to_layer(self, textures):

        if not textures:
            print("No textures to import.")
            return

        # Create a new fill layer in the active texture set
        current_stack_manager = vg_layerstack.VG_StackManager()
        new_layer = current_stack_manager.add_layer("fill", layer_position="On Top")
        new_layer.set_name("Stack layer")
        new_channel_set = new_layer.active_channels
        new_channel_set.remove(layerstack.ChannelType.Normal)
        new_layer.active_channels = set(new_channel_set)

        # Import and assign textures to the new fill layer
        texture_resource = None
        for texture_list_key in textures.textures.keys():
            current_texture_list = textures.textures[texture_list_key]

            for texture_path in current_texture_list:
                texture_resource = resource.import_project_resource(
                    texture_path, resource.Usage.TEXTURE
                )

                # Get the target channel type
                last_underscore_index = texture_path.rfind("_")
                extension_index = texture_path.rfind(".png")
                if last_underscore_index != -1 and extension_index != -1:
                    channel_type_string = texture_path[
                        last_underscore_index + 1 : extension_index
                    ]
                    channel_type_string = channel_type_string.split(".")[0]

                    if channel_type_string != "Normal":
                        channel_type = getattr(
                            layerstack.ChannelType, channel_type_string
                        )
                        new_layer.set_source(
                            channel_type, texture_resource.identifier()
                        )

        print("Textures imported and assigned to the new fill layer.")


if __name__ == "__main__":
    export_path = os.path.join(
        os.getenv("USERPROFILE"), "Documents/Adobe/Adobe Substance 3D Painter/export"
    )
    export_preset_name = "PBR Metallic Roughness"

    exporter = VG_ExportManager(export_path, export_preset_name)
    exported_textures = exporter.export_active_texture_set()

    if exported_textures:
        exporter.import_textures_to_layer(exported_textures)

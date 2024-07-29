##########################################################################
# 
# Copyright 2010-2024 Vincent GAULT - Adobe
# All Rights Reserved.
#
##########################################################################



import os
from substance_painter import project, export, textureset, resource, layerstack
import vg_pt_utils
import vg_pt_utils.vg_layerstack

class VG_ExportManager:
    """
    A manager gathering different features related to export in Substance 3D Painter.

    Attributes:
        export_path (str): The path where textures will be exported.
        export_preset_name (str): The name of the export preset to use.
    
    Methods:
        get_export_preset():
            Obtains the URL of the specified export preset.
        
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
            export_preset = resource.ResourceID(context="starter_assets", name=self.export_preset_name)
            return export_preset.url()
        except Exception as e:
            print(f"Error obtaining export preset: {e}")
            return None

    
    
    
    def export_active_texture_set(self):
        export_preset_url = self.get_export_preset()
        
        if export_preset_url is None:
            print("export_preset_url is None")
            return None

        # Get the active texture set
        texture_set = textureset.get_active_stack()
        texture_set_name = str(texture_set.material())
        

        
        # Configure the export settings
        export_config = {
            "exportShaderParams": False,
            "exportPath": self.export_path,
            "defaultExportPreset": export_preset_url,
            "exportList": [
                {
                    "rootPath": texture_set_name
                }],
            "exportParameters": [
                {
                    "parameters": {
                        "dithering": True,
                        "paddingAlgorithm": "infinite"
                    }
                }]
        }
        
        try:
            # Perform the export
            current_textureset = texture_set.material()
            
            if current_textureset.has_uv_tiles():
                print("UV tiles not supported yet")
            else:
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
        current_stack_manager = vg_pt_utils.vg_layerstack.VG_StackManager()
        new_layer = current_stack_manager.add_layer('fill', layer_position="On Top")
        new_layer.set_name("Stack layer")
        new_channel_set = new_layer.active_channels
        new_channel_set.remove(layerstack.ChannelType.Normal)
        new_layer.active_channels = set(new_channel_set)
        

        # Import and assign textures to the new fill layer                
        texture_resource = None
        for texture_list_key in textures.textures.keys():
            current_texture_list = textures.textures[texture_list_key]
            
            for texture_path in current_texture_list:
                texture_resource = resource.import_project_resource(texture_path,resource.Usage.TEXTURE)
                
                #Get the target channel type                
                last_underscore_index = texture_path.rfind('_')
                extension_index = texture_path.rfind('.png')
                if last_underscore_index != -1 and extension_index != -1:
                    channel_type_string = texture_path[last_underscore_index + 1:extension_index]
                    if channel_type_string != "Normal":
                        channel_type = getattr(layerstack.ChannelType, channel_type_string)
                        new_layer.set_source(channel_type, texture_resource.identifier())

        print("Textures imported and assigned to the new fill layer.")
        
        
        

if __name__ == "__main__":
    export_path = os.path.join(os.getenv('USERPROFILE'), 'Documents/Adobe/Adobe Substance 3D Painter/export')
    export_preset_name = "PBR Metallic Roughness"

    exporter = VG_ExportManager(export_path, export_preset_name)
    exported_textures = exporter.export_active_texture_set()
    
    
    if exported_textures:
        exporter.import_textures_to_layer(exported_textures)
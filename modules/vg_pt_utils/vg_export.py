##########################################################################
# 
# Copyright 2010-2024 Vincent GAULT - Adobe
# All Rights Reserved.
#
##########################################################################
"""
This module contains different utilities related to export in
Substance 3d Painter.
"""


# Modules Import
from substance_painter import export, project, resource, textureset

def export_all_active_channels():
    
    if project.is_open():
        # Retrieve all predefined export presets
        predefined_presets = export.list_predefined_export_presets()
               
        #document channels preset
        chosen_preset = predefined_presets[1]
        
        
        
        stack = textureset.get_active_stack()
        print(chosen_preset.list_output_maps(stack))
        export.export_project_textures()
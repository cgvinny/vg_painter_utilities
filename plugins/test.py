import pathlib
import substance_painter.event as spevent
import substance_painter.ui as spui
import substance_painter.project as sspproject
import substance_painter.baking as spbaking
import substance_painter.textureset as sptextureset
import time 

class SmoothBakingWorkflow:

    def __init__(self):
        spevent.DISPATCHER.connect(spevent.ProjectEditionEntered, SmoothBakingWorkflow.on_project_created) 

    def on_finish_baking(e):
            mode_painting = spui.UIMode(1)
            spui.switch_to_mode(mode_painting)
            print("switch to painting mode")

    
    def on_project_created(e): 

        template_path = sspproject.file_path()
        template_name = pathlib.Path(template_path).stem
        print(f'template name: {template_name}')

        template_tags = ["_noBake", "_autoBake", "_customBake"]

        mode_baking = spui.UIMode(4)
        

        # _customBake
        if template_tags[2] in template_name:

            spui.switch_to_mode(mode_baking)
            print("switch to baking mode")

        # _autoBake : new project > bake with standard settings, auto select mesh with the "_high" suffix > go to painting mode
        # 
        if template_tags[1] in template_name:

            spui.switch_to_mode(mode_baking)

            # With the sourceMesh_name, I search the project_sourceMesh_path to see if there is a correspondance
            # Except I discard the suffixe "_low" and test for the presence of "_high" in it's place
            
            project_sourceMesh_path = sspproject.last_imported_mesh_path()
            print(f'Project Source Mesh path: {project_sourceMesh_path}')

            sourceMesh_path = pathlib.Path(project_sourceMesh_path).parent
            print (f'Source Mesh path: {sourceMesh_path}')
            
            sourceMesh_name = pathlib.Path(project_sourceMesh_path).stem
            print(f'Source Mesh name: {sourceMesh_name}')

            # Remove the "_low" suffix from the source mesh name to get the high poly mesh name
            highpolyMesh_name = sourceMesh_name.replace("_low", "_high")
            print(f'High poly Mesh name: {highpolyMesh_name}')

            # Define excluded file extensions
            excluded_extensions = [".assbin"]

            # Search for the high poly in the low poly folder
            # Form the path for the high poly mesh by replacing the filename in sourceMesh_path
            highpolyMesh_path = None
            for file in sourceMesh_path.glob(f"{highpolyMesh_name}*"):
                if file.is_file() and not any(file.suffix == ext for ext in excluded_extensions):
                    highpolyMesh_path = str(file).replace("\\", "/")
                
                    
                    break

            if highpolyMesh_path:

                print(f"High poly mesh found at: {highpolyMesh_path}")                
                #print(common_params["HipolyMesh"].value())
                # Get all the necessary parameters preparing for the baking stage
                texture_set_list = sptextureset.all_texture_sets() #this gives back a list of all the texture sets
                baking_params = spbaking.BakingParameters.from_texture_set_name(str(texture_set_list[0])) # Setting only one high poly for all the texture sets 
                common_params = baking_params.common()
                spbaking.BakingParameters.set({common_params['HipolyMesh']:f'file:///{highpolyMesh_path}'})
                
                
                #time.sleep(10)

                # Here, I should test for the presence of the file > for Instance when using OneDrive, my file is sometimes not downloaded and this result in a warning


            
            for texture_set_name in texture_set_list:

                
                print(texture_set_name)
                
                
            else:
                print("High poly mesh not found in the low poly folder.")



            """ 
            
            
            
            """
            
            spevent.DISPATCHER.connect(spevent.BakingProcessEnded, SmoothBakingWorkflow.on_finish_baking)

            
            
            spbaking.bake_selected_textures_async()

    def __del__(self):
            pass
    
SMOOTH_BAKING_WORKFLOW = None


def start_plugin():
    """This method is called when the plugin is started."""
    global SMOOTH_BAKING_WORKFLOW
    SMOOTH_BAKING_WORKFLOW = SmoothBakingWorkflow()



def close_plugin():
    """This method is called when the plugin is stopped."""
    global SMOOTH_BAKING_WORKFLOW
    del SMOOTH_BAKING_WORKFLOW


if __name__ == "__main__":
    start_plugin()
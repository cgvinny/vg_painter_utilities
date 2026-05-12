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
import pathlib
from substance_painter import export, textureset, resource, layerstack, logging, colormanagement, ui, project
from PySide6 import QtWidgets, QtGui, QtCore
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
                logging.warning(f"VG Export: could not delete texture file '{texture_path}': {e}")


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
                logging.error(f"VG Export: texture export failed: {export_result.message}")
                return None
            return export_result
        except Exception as e:
            logging.error(f"VG Export: texture export failed: {e}")
            return None


class IDColorSwapDialog(QtWidgets.QDialog):
    """Dialog for picking a source color and a replacement color for ID map swapping."""

    def __init__(self, parent=None):
        super().__init__(parent or ui.get_main_window())
        self.setWindowTitle("ID Color Swap")
        self.setFixedWidth(280)
        self._source = QtGui.QColor.fromRgbF(1.0, 0.0, 0.0)
        self._target = QtGui.QColor.fromRgbF(0.0, 1.0, 0.0)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)

        swatches = QtWidgets.QHBoxLayout()
        swatches.setSpacing(16)
        self._src_btn = self._make_swatch_column(swatches, "Current color", self._source)
        self._tgt_btn = self._make_swatch_column(swatches, "New color", self._target)
        layout.addLayout(swatches)

        self._src_btn.clicked.connect(self._pick_source)
        self._tgt_btn.clicked.connect(self._pick_target)
        layout.addSpacing(4)

        swap_btn = QtWidgets.QPushButton("Swap Color")
        swap_btn.setDefault(True)
        swap_btn.clicked.connect(self.accept)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(swap_btn)
        layout.addLayout(btn_row)

    def _make_swatch_column(self, parent_layout, label_text, color):
        col = QtWidgets.QVBoxLayout()
        col.setSpacing(4)
        lbl = QtWidgets.QLabel(label_text)
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        btn = QtWidgets.QPushButton()
        btn.setFixedSize(100, 60)
        btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._apply_color(btn, color)
        col.addWidget(lbl)
        col.addWidget(btn)
        parent_layout.addLayout(col)
        return btn

    @staticmethod
    def _apply_color(btn, qcolor):
        pix = QtGui.QPixmap(btn.width() or 100, btn.height() or 60)
        pix.fill(qcolor)
        btn.setIcon(QtGui.QIcon(pix))
        btn.setIconSize(btn.size())

    def _pick_source(self):
        qc = QtWidgets.QColorDialog.getColor(
            self._source, self, "Current Color",
            QtWidgets.QColorDialog.DontUseNativeDialog,
        )
        if qc.isValid():
            self._source = qc
            self._apply_color(self._src_btn, qc)

    def _pick_target(self):
        qc = QtWidgets.QColorDialog.getColor(
            self._target, self, "New Color",
            QtWidgets.QColorDialog.DontUseNativeDialog,
        )
        if qc.isValid():
            self._target = qc
            self._apply_color(self._tgt_btn, qc)

    def source_color(self):
        return colormanagement.Color(self._source.redF(), self._source.greenF(), self._source.blueF())

    def target_color(self):
        return colormanagement.Color(self._target.redF(), self._target.greenF(), self._target.blueF())


##### FUNCTIONS USING THE CLASSES #####

def _build_id_map_export_config(ts_info):
    """Build the export config dict for a BaseColor-only (ID map) export."""
    udim_suffix = '.$udim' if ts_info.texture_set.has_uv_tiles() else ''
    return {
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
        exported = TextureExporter().export_textures(_build_id_map_export_config(ts_info))
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


def swap_id_map_color(source_color, target_color):
    """
    Replace source_color with target_color in the active texture set's ID map.

    Builds a temporary group with the existing ID map as a fill layer at the
    bottom and a new-color fill layer at the top masked by a Color Selection
    effect targeting source_color. Exports the group as a new ID map, updates
    the mesh map slot, then removes the temporary group.

    Args:
        source_color (colormanagement.Color): The ID color to replace.
        target_color (colormanagement.Color): The replacement color.
    """
    from PySide6 import QtWidgets
    from substance_painter import ui

    current_stack = textureset.get_active_stack()
    id_map_resource = current_stack.material().get_mesh_map_resource(textureset.MeshMapUsage.ID)

    if id_map_resource is None:
        QtWidgets.QMessageBox.warning(
            ui.get_main_window(),
            "ID Color Swap",
            "No ID map found on this texture set. Bake an ID map first.",
        )
        return

    root_nodes = layerstack.get_root_layer_nodes(current_stack)
    saved_visibility = [(node, node.is_visible()) for node in root_nodes]
    saved_selection = layerstack.get_selected_nodes(current_stack)

    temp_group = None
    texture_path = None
    try:
        # Create temp group at top of stack (root_nodes captured before insertion)
        temp_pos = layerstack.InsertPosition.from_textureset_stack(current_stack)
        temp_group = layerstack.insert_group(temp_pos)
        temp_group.set_name("ID Color Swap [Temp]")

        # Bottom fill layer: displays the existing ID map
        id_layer_pos = layerstack.InsertPosition.inside_node(
            temp_group, layerstack.NodeStack.Substack
        )
        id_layer = layerstack.insert_fill(id_layer_pos)
        id_layer.set_name("ID Map")
        id_layer.active_channels = {textureset.ChannelType.BaseColor}
        id_layer.set_source(layerstack.ChannelType.BaseColor, id_map_resource)

        # Top fill layer: the replacement color
        color_layer_pos = layerstack.InsertPosition.above_node(id_layer)
        color_layer = layerstack.insert_fill(color_layer_pos)
        color_layer.set_name("New Color")
        color_layer.active_channels = {textureset.ChannelType.BaseColor}
        color_layer.set_source(layerstack.ChannelType.BaseColor, target_color)

        # Black mask + Color Selection effect targeting source_color on the ID map
        color_layer.add_mask(layerstack.MaskBackground.Black)
        mask_pos = layerstack.InsertPosition.inside_node(
            color_layer, layerstack.NodeStack.Mask
        )
        cs_effect = layerstack.insert_color_selection_effect(mask_pos)
        default_params = cs_effect.get_parameters()
        cs_effect.set_parameters(layerstack.ColorSelectionEffectParams(
            id_mask=id_map_resource,
            output_value=1.0,
            hardness=default_params.hardness,
            tolerance=default_params.tolerance,
            background_color=layerstack.ColorSelectionBackgroundColor.Black,
            colors=[source_color],
        ))

        # Hide all pre-existing root nodes so only temp_group is composited
        for node in root_nodes:
            node.set_visible(False)

        # Export temp_group as a new ID map (BaseColor only)
        layerstack.set_selected_nodes([temp_group])
        ts_info = vg_project_info.TextureSetInfo().get_info()
        exported = TextureExporter().export_textures(_build_id_map_export_config(ts_info))
        if not exported:
            return

        texture_paths = [p for paths in exported.textures.values() for p in paths]
        if not texture_paths:
            return

        texture_path = texture_paths[0]
        imported = resource.import_project_resource(texture_path, resource.Usage.TEXTURE)
        ts_info.texture_set.set_mesh_map_resource(
            textureset.MeshMapUsage.ID, imported.identifier()
        )

    except Exception as e:
        QtWidgets.QMessageBox.critical(
            ui.get_main_window(), "ID Color Swap", f"An error occurred:\n{e}"
        )
    finally:
        if temp_group is not None:
            try:
                layerstack.delete_node(temp_group)
            except Exception:
                pass
        for node, was_visible in saved_visibility:
            try:
                node.set_visible(was_visible)
            except Exception:
                pass
        layerstack.set_selected_nodes(saved_selection)
        if texture_path is not None:
            try:
                os.remove(texture_path)
            except OSError:
                pass


def flatten_stack():
    """Flatten the stack by exporting its content, deleting all layers, and re-importing as a single fill layer."""
    export_config = ExportConfigGenerator(export.get_default_export_path()).generate_export_config()
    stack_manager = vg_layerstack.LayerManager()
    exported_textures = TextureExporter().export_textures(export_config)
    stack_manager.delete_stack_content()
    if exported_textures:
        _apply_textures_to_new_layer(stack_manager, exported_textures)


def save_viewport_thumbnail():
    """
    Grab the central viewport widget and save it as a PNG next to the .spp file.
    The output file takes the same base name as the project (e.g. my_project.png).
    Does nothing if the project has never been saved.
    """
    if not project.is_open():
        return

    spp_path = project.file_path()
    if not spp_path:
        QtWidgets.QMessageBox.warning(
            ui.get_main_window(),
            "Save Thumbnail",
            "Save the project first — the thumbnail is placed next to the .spp file.",
        )
        return

    save_path = pathlib.Path(spp_path).with_suffix(".png")

    central = ui.get_main_window().centralWidget()
    if central is None:
        logging.error("VG Export: could not locate the central viewport widget.")
        return

    pixmap = central.grab()
    if pixmap.isNull():
        logging.error("VG Export: viewport grab returned an empty image.")
        return

    if not pixmap.save(str(save_path)):
        logging.error(f"VG Export: could not write thumbnail to '{save_path}'.")
        return

    logging.info(f"VG Export: thumbnail saved → '{save_path}'")

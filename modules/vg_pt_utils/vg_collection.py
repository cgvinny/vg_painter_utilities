##########################################################################
#
# Copyright 2024 Vincent GAULT - Adobe
# All Rights Reserved.
#
##########################################################################

"""
Collection management for Substance 3D Painter.

A collection defines a named set of material slots, each linked to a color
in an ID map. Collections are stored on disk as a folder containing:
  - collection.json   (metadata + color chart)
  - <name>.spsm       (Smart Material with the full layer structure)

On-disk layout:
  collections/
    <SafeName>/
      collection.json
      <name>.spsm   (optional — created via save_as_smart_material())
"""

__author__ = "Vincent GAULT - Adobe"

import json
import pathlib
import shutil
import time
from dataclasses import dataclass, field
from typing import List, Optional

from substance_painter import layerstack, textureset, project, colormanagement, logging

from vg_pt_utils import vg_settings

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Root of the "Adobe Substance 3D Painter" user folder
# __file__ = .../Adobe Substance 3D Painter/python/modules/vg_pt_utils/vg_collection.py
_SP_ROOT = pathlib.Path(__file__).parent.parent.parent.parent

_COLLECTIONS_DIR = _SP_ROOT / "collections"

# Painter writes Smart Materials here when using "Save as Smart Material"
# (same folder on Windows and macOS — both live under the SP user documents root)
_SMART_MATERIALS_DIR = _SP_ROOT / "assets" / "smart-materials"

COLLECTION_JSON = "collection.json"


def collections_dir() -> pathlib.Path:
    """Return the root collections directory, creating it if needed."""
    _COLLECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    return _COLLECTIONS_DIR


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class CollectionSlot:
    """One material slot: a name and the RGB color of its ID map region."""
    material_name: str
    color: List[float]  # [r, g, b] in 0.0–1.0

    def to_dict(self):
        return {"material_name": self.material_name, "color": self.color}

    @classmethod
    def from_dict(cls, d: dict) -> "CollectionSlot":
        return cls(material_name=d["material_name"], color=d["color"])


@dataclass
class Collection:
    """A named collection of material slots with ID map color assignments."""
    name: str
    author: str
    description: str
    slots: List[CollectionSlot] = field(default_factory=list)

    def to_dict(self):
        return {
            "name": self.name,
            "author": self.author,
            "description": self.description,
            "slots": [s.to_dict() for s in self.slots],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Collection":
        return cls(
            name=d["name"],
            author=d.get("author", ""),
            description=d.get("description", ""),
            slots=[CollectionSlot.from_dict(s) for s in d.get("slots", [])],
        )

    def copy(self) -> "Collection":
        return Collection(
            name=self.name,
            author=self.author,
            description=self.description,
            slots=[CollectionSlot(s.material_name, list(s.color)) for s in self.slots],
        )


# ---------------------------------------------------------------------------
# Disk I/O
# ---------------------------------------------------------------------------

def _safe_folder_name(name: str) -> str:
    """Convert a collection name to a safe filesystem folder name."""
    return "".join(
        c if c.isalnum() or c in (" ", "-", "_") else "_" for c in name
    ).strip() or "Collection"


def get_collection_folder(collection_name: str) -> pathlib.Path:
    return collections_dir() / _safe_folder_name(collection_name)


def find_spsm(collection_name: str) -> Optional[pathlib.Path]:
    """
    Return the path of the most recently modified .spsm file in the collection
    folder, or None if none exists.

    Multiple .spsm files can accumulate when Painter holds a lock on the
    previous version (Windows WinError 33).  Always returning the newest one
    ensures the caller uses the latest saved version.
    """
    folder = get_collection_folder(collection_name)
    if not folder.exists():
        return None
    spsm_files = list(folder.glob("*.spsm"))
    if not spsm_files:
        return None
    return max(spsm_files, key=lambda p: p.stat().st_mtime)


def save_collection(collection: Collection) -> pathlib.Path:
    """
    Persist a collection's metadata to disk.

    Creates (or overwrites) collections/<SafeName>/collection.json.
    Returns the collection folder path.
    """
    if not collection.name.strip():
        raise ValueError("Collection name must not be empty.")

    folder = get_collection_folder(collection.name)
    folder.mkdir(parents=True, exist_ok=True)

    json_path = folder / COLLECTION_JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(collection.to_dict(), f, indent=2, ensure_ascii=False)

    return folder


def load_collection(folder_path: pathlib.Path) -> Optional[Collection]:
    """
    Load a collection from a folder path.

    Returns None if the JSON is missing or malformed.
    """
    json_path = folder_path / COLLECTION_JSON
    if not json_path.exists():
        return None
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Collection.from_dict(data)
    except Exception as e:
        logging.warning(f"VG Collections: could not load '{json_path}': {e}")
        return None


def list_collections() -> List[Collection]:
    """Return all valid collections found in the collections directory, sorted by name."""
    pending = set(vg_settings.load_settings().get("pending_delete_collections", []))
    result = []
    for folder in sorted(collections_dir().iterdir()):
        if folder.is_dir():
            col = load_collection(folder)
            if col is not None and col.name not in pending:
                result.append(col)
    return result


def delete_collection(collection_name: str) -> bool:
    """
    Delete a collection folder from disk.

    Returns True if deleted, False if the folder was not found.
    Raises PermissionError (with a human-readable message) if any file in the
    folder is locked — typically because a .spsm was imported into the active
    Painter project and is still held open.

    The lock check happens *before* any file is removed, so the collection
    remains intact if deletion is not possible.
    """
    folder = get_collection_folder(collection_name)
    if not folder.exists():
        return False

    # Pre-check: try to open every file exclusively before deleting anything.
    # This prevents partial deletion (e.g. collection.json removed but .spsm locked).
    for f in folder.rglob("*"):
        if f.is_file():
            try:
                with open(f, "r+b"):
                    pass
            except PermissionError:
                raise PermissionError(
                    f"Cannot delete '{collection_name}': {f.name} is locked by Painter.\n\n"
                    f"This usually means the Smart Material is loaded in the current project.\n"
                    f"Remove it from the layer stack (or close the project), then try again."
                )

    shutil.rmtree(folder)
    return True


def mark_for_deletion(collection_name: str) -> None:
    """Record a collection as pending deletion for the next Painter startup."""
    settings = vg_settings.load_settings()
    pending = settings.setdefault("pending_delete_collections", [])
    if collection_name not in pending:
        pending.append(collection_name)
    vg_settings.save_settings(settings)


def flush_pending_deletions() -> None:
    """Attempt to delete collections marked for deletion. Silently skips any still locked."""
    settings = vg_settings.load_settings()
    pending = settings.get("pending_delete_collections", [])
    if not pending:
        return

    remaining = []
    for name in pending:
        try:
            delete_collection(name)
            logging.info(f"VG Collections: deferred deletion of '{name}' completed.")
        except PermissionError:
            remaining.append(name)
        except Exception as e:
            logging.warning(f"VG Collections: could not delete pending collection '{name}': {e}")

    settings["pending_delete_collections"] = remaining
    vg_settings.save_settings(settings)


def duplicate_collection(source_name: str, new_name: str) -> pathlib.Path:
    """
    Duplicate a collection under a new name.

    Copies the source collection's metadata (with the new name) and its most
    recent .spsm file (if any) into a new folder.

    Returns the new collection folder path.
    Raises ValueError if the source collection is not found.
    Raises ValueError if a collection with new_name already exists.
    """
    source_folder = get_collection_folder(source_name)
    source_col = load_collection(source_folder)
    if source_col is None:
        raise ValueError(f"Source collection '{source_name}' not found.")

    new_folder = get_collection_folder(new_name)
    if new_folder.exists():
        raise ValueError(f"A collection named '{new_name}' already exists.")

    dup = Collection(
        name=new_name,
        author=source_col.author,
        description=source_col.description,
        slots=[CollectionSlot(s.material_name, list(s.color)) for s in source_col.slots],
    )
    save_collection(dup)

    source_spsm = find_spsm(source_name)
    if source_spsm is not None:
        shutil.copy2(source_spsm, new_folder / source_spsm.name)

    return new_folder


def rename_collection(old_name: str, new_collection: Collection) -> pathlib.Path:
    """
    Rename a collection: saves under the new name and removes the old folder.

    Returns the new folder path.
    """
    old_folder = get_collection_folder(old_name)
    new_folder = save_collection(new_collection)

    # If the folder names differ, copy any .spsm file then delete the old folder
    if old_folder.resolve() != new_folder.resolve() and old_folder.exists():
        old_spsm = find_spsm(old_name)
        if old_spsm:
            shutil.copy2(old_spsm, new_folder / old_spsm.name)
        shutil.rmtree(old_folder)

    return new_folder


# ---------------------------------------------------------------------------
# Layer stack helpers
# ---------------------------------------------------------------------------

def find_collection_group(collection_name: str):
    """
    Search the active texture set's root layer nodes for a group whose name
    matches *collection_name*.

    Returns the first matching GroupLayerNode (topmost in stack), or None.
    Requires a project to be open.
    """
    if not project.is_open():
        return None
    stack = textureset.get_active_stack()
    for node in layerstack.get_root_layer_nodes(stack):
        if (node.get_type() == layerstack.NodeType.GroupLayer
                and node.get_name() == collection_name):
            return node
    return None


def save_as_smart_material(collection_name: str, group_node) -> pathlib.Path:
    """
    Create a Smart Material from *group_node* via the Painter API and copy
    the resulting .spsm file into the collection folder.

    Painter writes the file to _SMART_MATERIALS_DIR (the user's
    "assets/smart-materials" folder).  This function detects the new file
    by diffing the directory contents before and after the API call, then
    copies it to ``collections/<SafeName>/``.

    Returns the destination path of the copied .spsm file.
    Raises RuntimeError if no new .spsm file is detected after creation.
    """
    sm_dir = _SMART_MATERIALS_DIR
    sm_dir.mkdir(parents=True, exist_ok=True)

    # Snapshot existing .spsm files before creation
    before: set = set(sm_dir.glob("*.spsm"))

    # Ask Painter to create the Smart Material.
    # If a same-named file is locked by Painter, it will create an incremented
    # copy (e.g. "name_1.spsm").  That is fine — we always take the most
    # recently written file and copy it to the collection folder under the
    # canonical name, so our collection folder always holds the latest version.
    layerstack.create_smart_material(group_node, collection_name)

    # Detect the newly written file
    after: set = set(sm_dir.glob("*.spsm"))
    new_files = after - before

    if not new_files:
        raise RuntimeError(
            f"Smart Material created but no new .spsm file was found in:\n"
            f"  {sm_dir}\n\n"
            f"Painter may have used a different folder. Check your Assets shelf "
            f"and copy the .spsm file to the collection folder manually."
        )

    # Always take the most recently modified file (handles incremented names)
    new_file = max(new_files, key=lambda p: p.stat().st_mtime)

    # Copy to collection folder with a timestamp suffix so we never try to
    # overwrite a file that Painter may have locked after a previous import.
    # find_spsm() always returns the most recently modified file, so the
    # next load will automatically pick up this new version.
    dest_folder = get_collection_folder(collection_name)
    dest_folder.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    dest = dest_folder / f"{collection_name}_{timestamp}.spsm"
    shutil.copy2(new_file, dest)

    logging.info(f"VG Collections: Smart Material saved → {dest}")
    return dest


# ---------------------------------------------------------------------------
# Layer structure builder
# ---------------------------------------------------------------------------

class CollectionLayerBuilder:
    """
    Builds the layer group structure in Painter for a given Collection.

    Result inside the active texture set:
      [Parent Group: collection.name]
        [Child Group: slot.material_name]  ← Black mask + Color Selection (slot color)
        [Child Group: slot.material_name]
        …

    The color selection effects are created with id_mask=None. To link them to the
    project's ID map, select each effect in the layer stack and choose the baked
    ID map via the Color Selection parameters panel.
    """

    def build(self, collection: Collection) -> tuple:
        """
        Insert the full collection structure into the active stack.

        Returns (parent_group_node, id_map_found: bool).
        Raises RuntimeError if no project is open.
        Raises ValueError if the collection has no slots.
        """
        if not project.is_open():
            raise RuntimeError("No project is open.")
        if not collection.slots:
            raise ValueError("The collection has no slots.")

        stack = textureset.get_active_stack()

        # Auto-detect the baked ID map for this texture set
        id_map_resource = stack.material().get_mesh_map_resource(
            textureset.MeshMapUsage.ID
        )

        # Parent group — inserted at the top of the stack
        parent_pos = layerstack.InsertPosition.from_textureset_stack(stack)
        parent_group = layerstack.insert_group(parent_pos)
        parent_group.set_name(collection.name)

        # Child groups — inserted in reverse order so slot[0] ends up on top
        for slot in reversed(collection.slots):
            child_pos = layerstack.InsertPosition.inside_node(
                parent_group, layerstack.NodeStack.Substack
            )
            child_group = layerstack.insert_group(child_pos)
            child_group.set_name(slot.material_name)

            # Black mask: only areas matching the ID color will be visible
            child_group.add_mask(layerstack.MaskBackground.Black)

            # Color Selection effect inside the mask
            mask_pos = layerstack.InsertPosition.inside_node(
                child_group, layerstack.NodeStack.Mask
            )
            cs_effect = layerstack.insert_color_selection_effect(mask_pos)

            # Configure the effect — connect the ID map if it is already baked
            r, g, b = slot.color[0], slot.color[1], slot.color[2]
            existing = cs_effect.get_parameters()
            params = layerstack.ColorSelectionEffectParams(
                id_mask=id_map_resource,
                output_value=1.0,
                hardness=existing.hardness,
                tolerance=existing.tolerance,
                background_color=layerstack.ColorSelectionBackgroundColor.Black,
                colors=[colormanagement.Color(r, g, b)],
            )
            cs_effect.set_parameters(params)

        layerstack.set_selected_nodes([parent_group])
        return parent_group, id_map_resource is not None

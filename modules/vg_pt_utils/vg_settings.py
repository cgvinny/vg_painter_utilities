##########################################################################
#
# Copyright 2010-2024 Vincent GAULT - Adobe
# All Rights Reserved.
#
##########################################################################

"""
Persistent settings for VG Utilities: keyboard shortcuts and general preferences.
Settings are stored as JSON in config/vg_settings.json relative to the python/ root.
"""
__author__ = "Vincent GAULT - Adobe"

import json
import copy
import pathlib

_CONFIG_PATH = pathlib.Path(__file__).parent.parent.parent / "config" / "vg_settings.json"

# All supported modifier combinations, in display order.
# Empty string means no modifier.
MODIFIER_OPTIONS = ["", "Ctrl", "Shift", "Alt", "Ctrl+Shift", "Ctrl+Alt", "Alt+Shift"]
MODIFIER_DISPLAY = {mod: mod if mod else "(none)" for mod in MODIFIER_OPTIONS}

# Ordered mapping of action IDs to human-readable menu labels.
# Order here drives the display order in the Settings dialog.
ACTION_LABELS = {
    "new_paint_layer":          "New Paint Layer",
    "new_fill_layer_base":      "New Fill Layer - Base Color",
    "new_fill_layer_height":    "New Fill Layer - Height",
    "new_fill_layer_all":       "New Fill Layer - All Channels",
    "new_fill_layer_empty":     "New Fill Layer - No Channel",
    "add_mask_popup":           "Add Mask...",
    "create_layer_from_stack":  "Create Layer from Visible Stack",
    "create_layer_from_group":  "Create Layer from Selected Group",
    "create_id_map_from_group": "Create ID Map from Selected Group",
    "flatten_stack":            "Flatten Stack",
    "create_ref_point_layer":   "Create Reference Point Layer",
    "launch_quick_bake":        "Quick Bake",
    "launch_bake_all":          "Bake All Texture Sets",
    "collection_panel":         "Collections — Open Panel",
}

DEFAULT_SETTINGS = {
    "shortcuts": {
        "new_paint_layer":          {"modifier": "Ctrl",        "key": "P"},
        "new_fill_layer_base":      {"modifier": "Ctrl",        "key": "F"},
        "new_fill_layer_height":    {"modifier": "Ctrl+Alt",    "key": "F"},
        "new_fill_layer_all":       {"modifier": "Ctrl+Shift",  "key": "F"},
        "new_fill_layer_empty":     {"modifier": "Alt",         "key": "F"},
        "add_mask_popup":           {"modifier": "Ctrl+Shift",  "key": "M"},
        "create_layer_from_stack":  {"modifier": "Ctrl+Shift",  "key": "G"},
        "create_layer_from_group":  {"modifier": "",            "key": ""},
        "create_id_map_from_group": {"modifier": "Ctrl+Shift",  "key": "I"},
        "flatten_stack":            {"modifier": "",            "key": ""},
        "create_ref_point_layer":   {"modifier": "Ctrl",        "key": "R"},
        "launch_quick_bake":        {"modifier": "Ctrl",        "key": "B"},
        "launch_bake_all":          {"modifier": "Ctrl+Shift",  "key": "B"},
        "collection_panel":         {"modifier": "",            "key": ""},
    },
    "ref_point": {
        "default_name_prefix": "REF POINT LAYER"
    },
    "pending_delete_collections": []
}


def load_settings():
    """Load settings from disk, merging saved values with defaults."""
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            return _deep_merge(DEFAULT_SETTINGS, saved)
        except Exception as e:
            print(f"VG Settings: could not load settings ({e}), using defaults.")
    return copy.deepcopy(DEFAULT_SETTINGS)


def save_settings(settings):
    """Persist settings to disk, creating the config directory if needed."""
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


def build_shortcut_string(modifier, key):
    """
    Return a QKeySequence-compatible string from a modifier and a key letter.
    Returns '' if key is empty.
    """
    if not key:
        return ""
    if not modifier:
        return key.upper()
    return f"{modifier}+{key.upper()}"


def _deep_merge(base, override):
    """Recursively merge *override* into *base*, returning a new dict."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result

##########################################################################
#
# Copyright 2010-2024 Vincent GAULT - Adobe
# All Rights Reserved.
#
##########################################################################

"""
Access to Painter's internal QActions via Qt widget tree introspection.

These actions are not part of the official substance_painter Python API.
They are discovered via main_window.findChildren(QAction) and are subject
to change across Painter versions. Use with caution.

--- Documented QActions (scanned on Painter, April 2026) ---

Notable non-checkable actions (triggerable):
  'Apply default brush'            — resets the active brush to defaults (appears twice)
  'Bake All Texture Sets'          — same as vg_baking.bake_all_texture_sets()

Notable checkable actions (toggle on/off):
  'Painting'                       sc=F9       — painting mode
  'Rendering (Iray)'               sc=F10      — Iray rendering mode
  'Bake Mesh Maps'                 sc=F8       — baking panel
  'Pause Engine Computation'       sc=Shift+Esc
  'Properties - Paint'             — paint properties panel
  'Texture Set Settings'           — texture set settings panel
  'Tools'                          — tools panel
  'Layers'                         — layers panel
  'Assets'                         — assets panel
  'Show/hide viewport interface'   — viewport HUD (Q key)
  'Brushes'                        — brushes panel

NOT found / not accessible:
  Stencil enable/disable           — absent from QAction tree entirely
  Brush properties (hardness, flow, spacing, jitter, alpha) — not exposed
"""
__author__ = "Vincent GAULT - Adobe"

from PySide6 import QtGui
from substance_painter import ui


def _find_actions_by_label(label):
    """
    Return all QActions in the main window whose text matches *label* exactly.
    There can be multiple instances (e.g. toolbar + menu duplicates).
    """
    results = []
    for action in ui.get_main_window().findChildren(QtGui.QAction):
        if action.text().strip() == label:
            results.append(action)
    return results


def apply_default_brush():
    """
    Trigger Painter's built-in 'Apply default brush' action.
    Equivalent to clicking the reset-brush button in the Properties panel.
    Raises RuntimeError if the action is not found.
    """
    actions = _find_actions_by_label("Apply default brush")
    if not actions:
        raise RuntimeError("'Apply default brush' action not found in Painter's UI.")
    actions[0].trigger()

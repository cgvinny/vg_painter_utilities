###############################################################################
# Organic Blending Panel — vg_organic_blending.py
# Creates a mask with Levels + Compare Mask effects on the selected layer
# to facilitate organic blending based on height maps.
###############################################################################
# Copyright 2024 Vincent GAULT - Adobe
# All Rights Reserved.
###############################################################################

"""
Dockable panel for the Organic Blending tool.

Activating the tool on a selected layer:
  1. Ensures the Normal channel is active with Normal blending mode.
  2. Adds a white mask to that layer.
  3. Inserts a Levels effect in Content (Height channel, full range).
  4. Inserts a Compare Mask effect in the mask stack.

Controls update both effects in real-time via valueChanged signals.
"""

__author__ = "Vincent GAULT - Adobe"

from typing import Optional

from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import Qt, Signal, QTimer

from substance_painter import ui, event, project, layerstack, textureset, logging
from substance_painter.layerstack import (
    InsertPosition,
    NodeStack,
    MaskBackground,
    CompareMaskEffectParams,
    CompareMaskEffectOperand,
    CompareMaskEffectOperation,
    FillLayerNode,
    UVTransformationParams,
    ScaleMode,
)
from substance_painter.levels import LevelsParamsMono
from substance_painter.textureset import ChannelType


# ---------------------------------------------------------------------------
# Shared stylesheet constants
# ---------------------------------------------------------------------------

_SLIDER_STYLE = """
QSlider::groove:horizontal {
    background: #3c3c3c;
    height: 2px;
    border-radius: 1px;
    margin: 0 2px;
}
QSlider::handle:horizontal {
    background: #b0b0b0;
    border: none;
    width: 12px;
    height: 12px;
    border-radius: 6px;
    margin: -5px 0;
}
QSlider::handle:horizontal:hover {
    background: #d4d4d4;
}
QSlider::handle:horizontal:disabled {
    background: #555;
}
QSlider::sub-page:horizontal {
    background: #686868;
    height: 2px;
    border-radius: 1px;
    margin: 0 2px;
}
"""

_SPINBOX_STYLE = """
QDoubleSpinBox {
    background: transparent;
    border: none;
    color: #b0b0b0;
    font-size: 12px;
    padding: 0;
}
QDoubleSpinBox:disabled { color: #555; }
QDoubleSpinBox::up-button,
QDoubleSpinBox::down-button { width: 0; height: 0; border: none; }
"""


# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------

class _OrganicState:
    """Holds live references to the layer and the two managed effect nodes."""

    def __init__(self, layer, layer_name: str, levels_node, compare_node):
        self.layer = layer
        self.layer_name = layer_name
        self.levels_node = levels_node
        self.compare_node = compare_node
        self.has_base_color = False
        self.has_fill_projection = False

    def is_valid(self) -> bool:
        """Return True if both effect nodes are still alive in the layer stack."""
        try:
            _ = self.levels_node.affected_channel
            _ = self.compare_node.get_parameters()
            return True
        except (ValueError, RuntimeError):
            return False


# ---------------------------------------------------------------------------
# Reusable widgets
# ---------------------------------------------------------------------------

class _ClickableSlider(QtWidgets.QSlider):
    """QSlider with two behaviors:
    - Click on handle → normal drag (Qt default).
    - Click on groove → jump to that position.
    """

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            opt = QtWidgets.QStyleOptionSlider()
            self.initStyleOption(opt)
            handle_rect = self.style().subControlRect(
                QtWidgets.QStyle.ComplexControl.CC_Slider,
                opt,
                QtWidgets.QStyle.SubControl.SC_SliderHandle,
                self,
            )
            if not handle_rect.contains(event.position().toPoint()):
                groove = self.style().subControlRect(
                    QtWidgets.QStyle.ComplexControl.CC_Slider,
                    opt,
                    QtWidgets.QStyle.SubControl.SC_SliderGroove,
                    self,
                )
                val = QtWidgets.QStyle.sliderValueFromPosition(
                    self.minimum(),
                    self.maximum(),
                    round(event.position().x()) - groove.x(),
                    groove.width(),
                )
                self.setValue(val)
                return
        super().mousePressEvent(event)


class _LabeledSlider(QtWidgets.QWidget):
    """Adobe-style slider: label + value on the top row, full-width slider below.

    Emits valueChanged(float) whenever the value changes.
    """

    valueChanged = Signal(float)

    def __init__(self, label: str, min_val: float, max_val: float,
                 step: float = 0.01, decimals: int = 2,
                 suffix: str = "", parent=None):
        super().__init__(parent)
        self._factor = round(1.0 / step)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 4)
        outer.setSpacing(3)

        # --- Header: label left, value right ---
        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(0)

        name_lbl = QtWidgets.QLabel(label)
        name_lbl.setStyleSheet("color: #b0b0b0; font-size: 12px;")
        header.addWidget(name_lbl, 1)

        self._spin = QtWidgets.QDoubleSpinBox()
        self._spin.setMinimum(min_val)
        self._spin.setMaximum(max_val)
        self._spin.setSingleStep(step)
        self._spin.setDecimals(decimals)
        if suffix:
            self._spin.setSuffix(f" {suffix}")
        self._spin.setStyleSheet(_SPINBOX_STYLE)
        self._spin.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._spin.setFixedWidth(80)
        header.addWidget(self._spin)

        outer.addLayout(header)

        # --- Slider ---
        self._slider = _ClickableSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(round(min_val * self._factor))
        self._slider.setMaximum(round(max_val * self._factor))
        self._slider.setStyleSheet(_SLIDER_STYLE)
        outer.addWidget(self._slider)

        self._updating = False
        self._slider.valueChanged.connect(self._on_slider)
        self._spin.valueChanged.connect(self._on_spin)

    def _on_slider(self, int_val: int):
        if self._updating:
            return
        self._updating = True
        val = int_val / self._factor
        self._spin.setValue(val)
        self._updating = False
        self.valueChanged.emit(val)

    def _on_spin(self, val: float):
        if self._updating:
            return
        self._updating = True
        self._slider.setValue(round(val * self._factor))
        self._updating = False
        self.valueChanged.emit(val)

    def value(self) -> float:
        return self._spin.value()

    def setValue(self, val: float):
        self._updating = True
        self._spin.setValue(val)
        self._slider.setValue(round(val * self._factor))
        self._updating = False

    def setMaximum(self, max_val: float):
        self._spin.setMaximum(max_val)
        self._slider.setMaximum(round(max_val * self._factor))
        if self._spin.value() > max_val:
            self.setValue(max_val)


# ---------------------------------------------------------------------------
# Main panel
# ---------------------------------------------------------------------------

class OrganicBlendingPanel(QtWidgets.QWidget):
    """Dockable Organic Blending panel."""

    WINDOW_TITLE = "Organic Blending"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setMinimumWidth(320)

        self._state: Optional[_OrganicState] = None
        self._applying = False
        self._last_stack = None

        self._build_ui()
        self._connect_events()
        self._set_active_state(False)

    # ------------------------------------------------------------------ UI --

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(6)

        # --- Status / activate row ---
        status_row = QtWidgets.QHBoxLayout()
        self._layer_label = QtWidgets.QLabel("No layer selected")
        self._layer_label.setStyleSheet("font-style: italic; color: #666; font-size: 12px;")
        status_row.addWidget(self._layer_label, 1)

        self._activate_btn = QtWidgets.QPushButton("Activate")
        self._activate_btn.setFixedWidth(84)
        self._activate_btn.clicked.connect(self._on_activate_toggle)
        status_row.addWidget(self._activate_btn)
        root.addLayout(status_row)

        # --- Separator ---
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        sep.setStyleSheet("color: #3a3a3a;")
        root.addWidget(sep)

        # --- Sliders ---
        self._top_amp_slider = _LabeledSlider(
            "Top Material Amplitude",
            min_val=0.0, max_val=100.0, step=1.0, decimals=0, suffix="%",
        )
        self._top_amp_slider.setValue(20.0)
        root.addWidget(self._top_amp_slider)

        self._height_slider = _LabeledSlider(
            "Level",
            min_val=0.0, max_val=1.0, step=0.01, decimals=2,
        )
        self._height_slider.setValue(0.5)
        root.addWidget(self._height_slider)

        self._hardness_slider = _LabeledSlider(
            "Hardness",
            min_val=0.0, max_val=1.0, step=0.01, decimals=2,
        )
        self._hardness_slider.setValue(0.9)
        root.addWidget(self._hardness_slider)

        self._inherit_color_slider = _LabeledSlider(
            "Inherit Color",
            min_val=0.0, max_val=100.0, step=1.0, decimals=0, suffix="%",
        )
        self._inherit_color_slider.setValue(0.0)
        root.addWidget(self._inherit_color_slider)

        self._scale_slider = _LabeledSlider(
            "Scale",
            min_val=0.1, max_val=10.0, step=0.1, decimals=1,
        )
        self._scale_slider.setValue(1.0)
        root.addWidget(self._scale_slider)

        root.addStretch()


    def _set_active_state(self, active: bool):
        if active and self._state is not None:
            self._layer_label.setText(self._state.layer_name)
            self._layer_label.setStyleSheet("font-weight: bold; color: #ccc; font-size: 12px;")
            self._activate_btn.setText("Deactivate")
        else:
            self._layer_label.setText("No layer selected")
            self._layer_label.setStyleSheet("font-style: italic; color: #666; font-size: 12px;")
            self._activate_btn.setText("Activate")

        for w in (self._top_amp_slider, self._height_slider, self._hardness_slider,
                  self._inherit_color_slider):
            w.setEnabled(active)
        self._scale_slider.setEnabled(
            active and self._state is not None and self._state.has_fill_projection
        )

    # ----------------------------------------------------------- Activation --

    def _on_activate_toggle(self):
        if self._state is not None:
            self._deactivate()
        else:
            self._activate()

    def _activate(self):
        if not project.is_open():
            return

        stack = textureset.get_active_stack()
        selected = layerstack.get_selected_nodes(stack)

        if not selected:
            QtWidgets.QMessageBox.warning(
                self, "Organic Blending",
                "Please select a layer first."
            )
            return

        if not stack.has_channel(ChannelType.Height):
            QtWidgets.QMessageBox.warning(
                self, "Organic Blending",
                "The active texture set does not have a Height channel.\n"
                "Please add a Height channel before activating Organic Blending."
            )
            return

        layer = selected[0]
        _normal_blend = layerstack.BlendingMode(2)

        # Force-activate Height, Normal, and BaseColor channels with Normal blend.
        current_channels = set(layer.active_channels)
        to_add = {ch for ch in (ChannelType.Height, ChannelType.Normal, ChannelType.BaseColor)
                  if stack.has_channel(ch) and ch not in current_channels}
        if to_add:
            layer.active_channels = current_channels | to_add
        for ch in (ChannelType.Height, ChannelType.Normal, ChannelType.BaseColor):
            if stack.has_channel(ch):
                layer.set_blending_mode(_normal_blend, ch)

        # Add white mask only if none exists yet.
        if not layer.has_mask():
            try:
                layer.add_mask(MaskBackground.White)
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Organic Blending",
                    f"Could not add mask to the selected layer:\n{e}"
                )
                return

        # Levels in Content stack → affects Height channel output.
        inside_content = InsertPosition.inside_node(layer, NodeStack.Content)
        levels_node = layerstack.insert_levels_effect(inside_content)
        levels_node.affected_channel = ChannelType.Height
        levels_node.set_parameters(LevelsParamsMono(
            input_min=-1.0, input_max=1.0, gamma=1.0,
            output_min=-1.0, output_max=1.0, clamp=True,
        ))

        # Compare Mask in mask stack.
        inside_mask = InsertPosition.inside_node(layer, NodeStack.Mask)
        compare_node = layerstack.insert_compare_mask_effect(inside_mask)

        layer_name = layer.get_name()
        self._state = _OrganicState(layer, layer_name, levels_node, compare_node)
        self._state.has_base_color = stack.has_channel(ChannelType.BaseColor)
        self._state.has_fill_projection = isinstance(layer, FillLayerNode)
        if self._state.has_fill_projection:
            try:
                proj = layer.get_projection_parameters()
                t = proj.uv_transformation
                if (t.scale_mode == ScaleMode.Factors
                        and t.scale is not None and len(t.scale) >= 1):
                    self._scale_slider.setValue(t.scale[0])
                else:
                    self._scale_slider.setValue(1.0)
            except Exception:
                self._scale_slider.setValue(1.0)
        self._last_stack = stack

        self._set_active_state(True)
        self._connect_value_signals()
        self._apply_to_effects()

    def _deactivate(self):
        self._disconnect_value_signals()
        self._state = None
        self._set_active_state(False)
        self._reset_sliders()

    def _reset_sliders(self):
        self._top_amp_slider.setValue(20.0)
        self._height_slider.setValue(0.5)
        self._hardness_slider.setValue(0.9)
        self._inherit_color_slider.setValue(0.0)
        self._scale_slider.setValue(1.0)

    # -------------------------------------------------- Live effect update --

    def _connect_value_signals(self):
        self._top_amp_slider.valueChanged.connect(self._apply_to_effects)
        self._height_slider.valueChanged.connect(self._apply_to_effects)
        self._hardness_slider.valueChanged.connect(self._apply_to_effects)
        self._inherit_color_slider.valueChanged.connect(self._apply_to_effects)
        self._scale_slider.valueChanged.connect(self._apply_to_effects)

    def _disconnect_value_signals(self):
        for sig, slot in [
            (self._top_amp_slider.valueChanged,       self._apply_to_effects),
            (self._height_slider.valueChanged,        self._apply_to_effects),
            (self._hardness_slider.valueChanged,      self._apply_to_effects),
            (self._inherit_color_slider.valueChanged, self._apply_to_effects),
            (self._scale_slider.valueChanged,         self._apply_to_effects),
        ]:
            try:
                sig.disconnect(slot)
            except RuntimeError:
                pass

    def _apply_to_effects(self, *_args):
        if self._state is None or self._applying:
            return
        if not self._state.is_valid():
            self._deactivate()
            return

        self._applying = True
        try:
            self._apply_levels()
            self._apply_compare()
            self._apply_inherit_color()
            self._apply_scale()
        except (ValueError, RuntimeError) as exc:
            logging.warning(f"Organic Blending: effect update failed — {exc}")
            self._deactivate()
        finally:
            self._applying = False

    def _apply_levels(self):
        # Preserve input range set by the user (e.g. via Auto in Painter's UI).
        current = self._state.levels_node.get_parameters()

        center = self._height_slider.value() * 2.0 - 1.0   # [0,1] → [-1,+1]
        half = self._top_amp_slider.value() / 100.0        # % → [0,1]

        # Compress spread to fit within [-1, +1]: at the extremes (center = ±1)
        # both bounds converge to the boundary, covering the material fully.
        half_eff = max(0.0, min(half, center + 1.0, 1.0 - center))

        params = LevelsParamsMono(
            input_min=current.input_min,
            input_max=current.input_max,
            gamma=current.gamma,
            output_min=center - half_eff,
            output_max=center + half_eff,
            clamp=True,
        )
        self._state.levels_node.set_parameters(params)

    def _apply_compare(self):
        params = CompareMaskEffectParams(
            channel=ChannelType.Height,
            left_operand=CompareMaskEffectOperand.ThisLayer,
            right_operand=CompareMaskEffectOperand.LayersBelow,
            operation=CompareMaskEffectOperation.GreaterThan,
            constant=0.0,
            tolerance=0.0,
            hardness=self._hardness_slider.value(),
        )
        self._state.compare_node.set_parameters(params)

    def _apply_inherit_color(self):
        if not self._state.has_base_color:
            return
        pct = self._inherit_color_slider.value()
        opacity = 1.0 - pct / 100.0
        self._state.layer.set_opacity(opacity, ChannelType.BaseColor)

    def _apply_scale(self):
        if not self._state.has_fill_projection:
            return
        scale = self._scale_slider.value()
        proj = self._state.layer.get_projection_parameters()
        proj.uv_transformation = UVTransformationParams(
            scale_mode=ScaleMode.Factors,
            scale=[scale, scale],
            rotation=proj.uv_transformation.rotation,
            offset=proj.uv_transformation.offset,
        )
        self._state.layer.set_projection_parameters(proj)

    # ------------------------------------------------------------ Events --

    def _connect_events(self):
        event.DISPATCHER.connect_strong(
            event.LayerStacksModelDataChanged, self._on_data_changed
        )
        event.DISPATCHER.connect_strong(
            event.ProjectClosed, self._on_project_closed
        )
        self._stack_timer = QTimer(self)
        self._stack_timer.setInterval(500)
        self._stack_timer.timeout.connect(self._check_active_stack)
        self._stack_timer.start()

    def _disconnect_events(self):
        for ev, cb in [
            (event.LayerStacksModelDataChanged, self._on_data_changed),
            (event.ProjectClosed,               self._on_project_closed),
        ]:
            try:
                event.DISPATCHER.disconnect(ev, cb)
            except Exception:
                pass
        if hasattr(self, '_stack_timer'):
            self._stack_timer.stop()

    def _check_active_stack(self):
        """Deactivate if the user switched to a different texture set."""
        if not project.is_open():
            return
        try:
            current = textureset.get_active_stack()
        except Exception:
            return
        if current != self._last_stack:
            self._last_stack = current
            if self._state is not None:
                self._deactivate()

    def _on_data_changed(self, _e):
        if self._state is not None and not self._state.is_valid():
            self._deactivate()

    def _on_project_closed(self, _e):
        self._last_stack = None
        if self._state is not None:
            self._disconnect_value_signals()
            self._state = None
            self._set_active_state(False)

    # ------------------------------------------------------------ Cleanup --

    def cleanup(self):
        self._disconnect_events()
        if self._state is not None:
            self._disconnect_value_signals()
            self._state = None

    def closeEvent(self, event_):
        self.cleanup()
        super().closeEvent(event_)

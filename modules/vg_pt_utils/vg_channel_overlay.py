###############################################################################
# Channel Overlay — vg_channel_overlay.py
# Semi-transparent HUD strip showing texture-set channels, anchored bottom-right.
###############################################################################
# Copyright 2024 Vincent GAULT - Adobe
# All Rights Reserved.
###############################################################################

__author__ = "Vincent GAULT - Adobe"

from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt, QEvent, QPoint, QTimer

import substance_painter.project as project
import substance_painter.textureset as textureset
import substance_painter.layerstack as layerstack
import substance_painter.event as sp_event
from substance_painter import event
from substance_painter.textureset import ChannelType, ChannelFormat

from vg_pt_utils import vg_settings


# ---------------------------------------------------------------------------
# Channel metadata
# ---------------------------------------------------------------------------

_CHANNEL_LABELS = {
    "BaseColor":        "Base Col",
    "Height":           "Height",
    "Specular":         "Specular",
    "SpecularEdgeColor":"Spec Edge",
    "Opacity":          "Opacity",
    "Emissive":         "Emissive",
    "Displacement":     "Displace",
    "Glossiness":       "Gloss",
    "Roughness":        "Rough",
    "Anisotropylevel":  "Aniso",
    "Anisotropyangle":  "Aniso Ang",
    "Transmissive":     "Transmit",
    "Reflection":       "Reflect",
    "Ior":              "IOR",
    "Metallic":         "Metallic",
    "Normal":           "Normal",
    "AO":               "AO",
    "Diffuse":          "Diffuse",
    "Specularlevel":    "Spec Lvl",
    "BlendingMask":     "Blend",
    "Translucency":     "Transluc",
    "Scattering":       "Scatter",
    "ScatterColor":     "Scat Col",
    "SheenOpacity":     "Sh Opac",
    "SheenRoughness":   "Sh Rough",
    "SheenColor":       "Sh Col",
    "CoatOpacity":      "Co Opac",
    "CoatColor":        "Co Col",
    "CoatRoughness":    "Co Rough",
    "CoatSpecularLevel":"Co Spec",
    "CoatNormal":       "Co Norm",
}

# Explicit list of all ChannelType members — ChannelType is a pybind11 type
# and cannot be iterated like a Python enum.
def _build_all_channel_types() -> list:
    names = [
        "BaseColor", "Height", "Specular", "SpecularEdgeColor", "Opacity",
        "Emissive", "Displacement", "Glossiness", "Roughness",
        "Anisotropylevel", "Anisotropyangle", "Transmissive", "Reflection",
        "Ior", "Metallic", "Normal", "AO", "Diffuse", "Specularlevel",
        "BlendingMask", "Translucency", "Scattering", "ScatterColor",
        "SheenOpacity", "SheenRoughness", "SheenColor",
        "CoatOpacity", "CoatColor", "CoatRoughness", "CoatSpecularLevel", "CoatNormal",
        "User0", "User1", "User2", "User3", "User4", "User5", "User6", "User7",
        "User8", "User9", "User10", "User11", "User12", "User13", "User14", "User15",
    ]
    result = []
    for name in names:
        ct = getattr(ChannelType, name, None)
        if ct is not None:
            result.append(ct)
    return result

_ALL_CHANNEL_TYPES: list = _build_all_channel_types()


# Channel color swatches — approximate visual mapping inspired by Painter's
# native channel iconography. Used as small colored dots prefixed to each button.
_CHANNEL_COLORS: dict[str, str] = {
    "BaseColor":         "#D97557",
    "Specular":          "#E8E8E8",
    "SpecularEdgeColor": "#E0D8C8",
    "Opacity":           "#7AB8D6",
    "Emissive":          "#E8C040",
    "Displacement":      "#6B6B6B",
    "Glossiness":        "#A8A8A8",
    "Roughness":         "#888888",
    "Anisotropylevel":   "#9080A0",
    "Anisotropyangle":   "#B098B8",
    "Transmissive":      "#90D8B0",
    "Reflection":        "#B8E0E8",
    "Ior":               "#C0A8D8",
    "Metallic":          "#C0C0C0",
    "Normal":            "#8088C8",
    "Height":            "#605040",
    "AO":                "#6B4A3A",
    "Diffuse":           "#D0A088",
    "Specularlevel":     "#DCDCDC",
    "BlendingMask":      "#404040",
    "Translucency":      "#A0D8C0",
    "Scattering":        "#E0809A",
    "ScatterColor":      "#E098B0",
    "SheenOpacity":      "#9AC0D8",
    "SheenRoughness":    "#7090B0",
    "SheenColor":        "#80A8C0",
    "CoatOpacity":       "#D8C080",
    "CoatColor":         "#D8B070",
    "CoatRoughness":     "#A89060",
    "CoatSpecularLevel": "#C8B080",
    "CoatNormal":        "#807AB0",
}


# sRGB8 for color channels, L16F for data channels, L8 as default
_DEFAULT_FORMAT: dict[str, ChannelFormat] = {
    "BaseColor":        ChannelFormat.sRGB8,
    "Specular":         ChannelFormat.sRGB8,
    "SpecularEdgeColor":ChannelFormat.sRGB8,
    "Emissive":         ChannelFormat.sRGB8,
    "Diffuse":          ChannelFormat.sRGB8,
    "SheenColor":       ChannelFormat.sRGB8,
    "CoatColor":        ChannelFormat.sRGB8,
    "ScatterColor":     ChannelFormat.sRGB8,
    "Normal":           ChannelFormat.RGB8,
    "CoatNormal":       ChannelFormat.RGB8,
    "Height":           ChannelFormat.L16F,
    "Displacement":     ChannelFormat.L16F,
}


# ---------------------------------------------------------------------------
# Theme / stylesheets — driven by QApplication.palette()
# ---------------------------------------------------------------------------

def _lighten(qcolor: QtGui.QColor, amount: int) -> QtGui.QColor:
    """Return a copy of qcolor lightened by `amount` (0-255) on each channel."""
    return QtGui.QColor(
        max(0, min(255, qcolor.red() + amount)),
        max(0, min(255, qcolor.green() + amount)),
        max(0, min(255, qcolor.blue() + amount)),
    )


class _Theme:
    """Snapshot of palette-derived colors used to build all overlay stylesheets."""

    def __init__(self) -> None:
        app = QtWidgets.QApplication.instance()
        palette = app.palette() if app is not None else QtGui.QPalette()

        self.window   = palette.color(QtGui.QPalette.Window)
        self.base     = palette.color(QtGui.QPalette.Base)
        self.button   = palette.color(QtGui.QPalette.Button)
        self.mid      = palette.color(QtGui.QPalette.Mid)
        self.dark     = palette.color(QtGui.QPalette.Dark)
        self.text     = palette.color(QtGui.QPalette.WindowText)
        self.btn_text = palette.color(QtGui.QPalette.ButtonText)
        self.highlight     = palette.color(QtGui.QPalette.Highlight)
        self.highlight_txt = palette.color(QtGui.QPalette.HighlightedText)

        # Derived shades — slightly lighter / darker variants for hover
        self.button_hover  = _lighten(self.button, 18)
        self.highlight_hov = _lighten(self.highlight, 22)

    @staticmethod
    def _css(c: QtGui.QColor) -> str:
        return f"rgb({c.red()}, {c.green()}, {c.blue()})"

    # --- builders ----------------------------------------------------------

    def overlay_bg_style(self, object_name: str) -> str:
        return f"""
#{object_name} {{
    background-color: {self._css(self.window)};
    border: 1px solid {self._css(self.mid)};
    border-radius: 4px;
}}
"""

    def channel_btn_style(self, color_hex: str) -> str:
        return f"""
QPushButton {{
    background: {self._css(self.button)};
    color: {self._css(self.btn_text)};
    border: 1px solid {self._css(self.mid)};
    border-left: 3px solid {color_hex};
    border-radius: 2px;
    padding: 0px 4px;
    font-size: 10px;
    min-width: 0px;
    min-height: 0px;
}}
QPushButton:checked {{
    background: {self._css(self.highlight)};
    color: {self._css(self.highlight_txt)};
    border: 1px solid {self._css(self.highlight)};
    border-left: 3px solid {color_hex};
}}
QPushButton:hover:!checked {{
    background: {self._css(self.button_hover)};
}}
QPushButton:hover:checked {{
    background: {self._css(self.highlight_hov)};
}}
"""

    def add_btn_style(self) -> str:
        return f"""
QPushButton {{
    background: {self._css(self.button)};
    color: {self._css(self.btn_text)};
    border: 1px solid {self._css(self.mid)};
    border-radius: 2px;
    padding: 0px 2px;
    font-size: 10px;
    font-weight: bold;
    min-width: 0px;
    min-height: 0px;
}}
QPushButton:hover {{
    background: {self._css(self.button_hover)};
}}
"""

    def chevron_style(self) -> str:
        return f"""
QToolButton {{
    background: {self._css(self.button)};
    color: {self._css(self.btn_text)};
    border: 1px solid {self._css(self.mid)};
    border-radius: 2px;
    padding: 0px 2px;
    font-size: 11px;
    font-weight: bold;
}}
QToolButton:hover {{
    background: {self._css(self.button_hover)};
}}
"""


_MAX_PER_ROW = 6
_OVERLAY_OBJECT_NAME = "VgChannelOverlay"


# ---------------------------------------------------------------------------
# Overlay widget
# ---------------------------------------------------------------------------

class ChannelOverlay(QtWidgets.QWidget):
    """Translucent channel strip floating over the Painter 3D viewport.

    Implemented as a frameless Qt.Tool top-level window because Painter's
    viewport is a native Vulkan rendering surface — child Qt widgets parented
    to it would be hidden by the native paint. A Tool window stays associated
    with its parent (hides on minimize) and renders above it.
    """

    def __init__(self, main_window: QtWidgets.QWidget) -> None:
        super().__init__(
            main_window,
            Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setObjectName(_OVERLAY_OBJECT_NAME)

        # Pick up Painter's current Qt palette for a native look
        self._theme = _Theme()
        self.setStyleSheet(self._theme.overlay_bg_style(_OVERLAY_OBJECT_NAME))

        self._main_window = main_window
        self._buttons: dict[ChannelType, QtWidgets.QPushButton] = {}
        self._should_be_visible = False

        # Per-(node, channel) source cache. Used to restore the channel's content
        # when the user re-enables a channel they previously disabled via the
        # overlay — assigning to active_channels otherwise loses the source.
        # Key: (node_uid, ChannelType). Value: source returned by get_source().
        self._source_cache: dict[tuple, object] = {}

        # Cached size of the bar when last drawn expanded. Used to compute the
        # natural anchor position consistently across collapse / expand cycles.
        self._last_expanded_size: QtCore.QSize | None = None
        # Set to True by _rebuild when expanding; cleared once _reposition updates
        # _last_expanded_size from a settled layout (deferred call only).
        self._needs_size_update = False

        # Load persisted state
        settings = vg_settings.load_settings()
        self._collapsed = bool(settings.get("channel_overlay_collapsed", False))
        self._user_offset = (
            int(settings.get("channel_overlay_offset_x", 0)),
            int(settings.get("channel_overlay_offset_y", 0)),
        )

        # Drag state (set during mousePress, cleared on release)
        self._drag_origin: QPoint | None = None
        self._drag_window_origin: QPoint | None = None
        self._drag_active = False

        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(3, 2, 3, 2)
        layout.setSpacing(2)
        self._layout = layout

        self._collapse_btn = QtWidgets.QToolButton(self)
        self._collapse_btn.setStyleSheet(self._theme.chevron_style())
        self._collapse_btn.setMaximumWidth(16)
        self._collapse_btn.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self._collapse_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self._collapse_btn.customContextMenuRequested.connect(self._show_chevron_menu)
        # Click vs drag handled in eventFilter; do NOT connect clicked here.
        self._collapse_btn.installEventFilter(self)
        self._update_collapse_btn()

        self._add_btn = QtWidgets.QPushButton("+")
        self._add_btn.setStyleSheet(self._theme.add_btn_style())
        self._add_btn.setToolTip("Add channel to Texture Set")
        self._add_btn.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self._add_btn.adjustSize()
        self._add_btn.clicked.connect(self._show_add_menu)
        # Placement handled by _rebuild

        self._connect_sp_events()

        # Watch main window for move/resize, and the central widget for resize
        # (so the overlay tracks dock-panel resizes too)
        main_window.installEventFilter(self)
        central = main_window.centralWidget() if hasattr(main_window, "centralWidget") else None
        if central is not None:
            central.installEventFilter(self)

        # Hide the overlay when Painter loses application focus (switch to another app)
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.applicationStateChanged.connect(self._on_app_state_changed)

        # Poll selection every 500 ms to update opacity when layer type changes.
        # LayerStacksModelDataChanged may not fire on a bare selection click.
        self._selection_timer = QTimer(self)
        self._selection_timer.setInterval(500)
        self._selection_timer.timeout.connect(self._refresh_states)
        self._selection_timer.start()

        # Defer the first build so Qt has time to fully initialize the widget's
        # layout system. Calling _rebuild synchronously here makes adjustSize()
        # return a partial size on the first show, causing a visible right-shift
        # when the deferred reposition corrects it.
        QTimer.singleShot(0, self._rebuild)

    # ------------------------------------------------------------------
    # Substance Painter event handlers
    # ------------------------------------------------------------------

    def _connect_sp_events(self) -> None:
        event.DISPATCHER.connect_strong(sp_event.LayerStacksModelDataChanged, self._on_stack_changed)
        event.DISPATCHER.connect_strong(sp_event.ProjectOpened, self._on_project_opened)
        event.DISPATCHER.connect_strong(sp_event.ProjectAboutToClose, self._on_project_closed)

    def _on_stack_changed(self, e) -> None:
        if not project.is_open():
            self._rebuild()
            return
        try:
            stack = textureset.get_active_stack()
            current_types = set(stack.all_channels().keys())
        except Exception:
            self._rebuild()
            return
        if current_types != set(self._buttons.keys()):
            self._rebuild()
        else:
            self._refresh_states()

    def _on_project_opened(self, e) -> None:
        self._rebuild()

    def _on_project_closed(self, e) -> None:
        self._rebuild()

    # ------------------------------------------------------------------
    # Resize tracking
    # ------------------------------------------------------------------

    def eventFilter(self, obj, qevent) -> bool:
        t = qevent.type()

        # Drag handling on the chevron — distinguishes click from drag
        if obj is self._collapse_btn:
            if t == QEvent.Type.MouseButtonPress and qevent.button() == Qt.LeftButton:
                self._drag_origin = qevent.globalPosition().toPoint()
                self._drag_window_origin = self.pos()
                return False  # let button track its own pressed state
            if t == QEvent.Type.MouseMove and self._drag_origin is not None:
                delta = qevent.globalPosition().toPoint() - self._drag_origin
                if abs(delta.x()) > 4 or abs(delta.y()) > 4:
                    self.move(self._drag_window_origin + delta)
                    self._drag_active = True
                    return True
            if t == QEvent.Type.MouseButtonRelease and qevent.button() == Qt.LeftButton:
                if self._drag_origin is not None:
                    was_drag = self._drag_active
                    self._drag_origin = None
                    self._drag_window_origin = None
                    self._drag_active = False
                    if was_drag:
                        # Persist offset: how far did the user move from the natural left-edge position
                        nat_x, nat_y = self._natural_left_top()
                        self._user_offset = (
                            self.pos().x() - nat_x,
                            self.pos().y() - nat_y,
                        )
                        self._save_offset()
                        return True
                    # Not a drag — perform the collapse toggle ourselves
                    self._toggle_collapse()
                    return True

        if t in (
            QEvent.Type.Resize,
            QEvent.Type.Move,
            QEvent.Type.Show,
            QEvent.Type.WindowStateChange,
        ):
            self._reposition()
        elif t == QEvent.Type.Hide and obj is self._main_window:
            self.hide()
        return False

    def _save_offset(self) -> None:
        s = vg_settings.load_settings()
        s["channel_overlay_offset_x"] = self._user_offset[0]
        s["channel_overlay_offset_y"] = self._user_offset[1]
        vg_settings.save_settings(s)

    def _show_chevron_menu(self) -> None:
        menu = QtWidgets.QMenu(self)
        reset_action = menu.addAction("Reset position")
        reset_action.triggered.connect(self._reset_position)
        menu.exec(QtGui.QCursor.pos())

    def _reset_position(self) -> None:
        self._user_offset = (0, 0)
        self._save_offset()
        self._last_expanded_size = None
        self._needs_size_update = True
        self._reposition()
        QTimer.singleShot(0, self._reposition)

    def reset_position(self) -> None:
        """Public method — called from the launcher menu item."""
        self._reset_position()

    def _on_app_state_changed(self, state) -> None:
        if state == Qt.ApplicationActive:
            if self._should_be_visible:
                self.show()
                self._reposition()
        else:
            super().hide()

    def _viewport_rect_global(self) -> QtCore.QRect:
        """Compute the viewport's screen rect (excluding side/bottom dock panels).

        Strategy:
          1. Start from the central widget's geometry if available (this already
             accounts for menubar, toolbar, and the dock-widget margins).
          2. Walk visible children of the main window and shrink the rect by any
             widget that looks like a docked panel (touches an edge and doesn't
             span the opposite axis). Catches Painter's non-QDockWidget panels.
        """
        mw = self._main_window

        # 1. Base rect — central widget in global coords if it looks usable
        central = mw.centralWidget() if hasattr(mw, "centralWidget") else None
        if central is not None and central.isVisible() and central.width() > 50:
            tl = central.mapToGlobal(QPoint(0, 0))
            rect = QtCore.QRect(tl.x(), tl.y(), central.width(), central.height())
        else:
            tl = mw.mapToGlobal(QPoint(0, 0))
            rect = QtCore.QRect(tl.x(), tl.y(), mw.width(), mw.height())

        # 2. Subtract docked panels detected by geometry on the main window
        mw_tl = mw.mapToGlobal(QPoint(0, 0))
        mw_w, mw_h = mw.width(), mw.height()
        edge = 4  # tolerance in pixels for "touches edge"

        for child in mw.children():
            if not isinstance(child, QtWidgets.QWidget):
                continue
            if not child.isVisible() or child is self:
                continue
            geo = child.geometry()  # main-window local coords
            if geo.isEmpty() or geo.width() < 30 or geo.height() < 30:
                continue
            spans_w = geo.width()  > mw_w * 0.6
            spans_h = geo.height() > mw_h * 0.6

            # Side panels: touch a vertical edge, don't span horizontally
            touches_right  = geo.right()  >= mw_w - edge
            touches_left   = geo.left()   <= edge
            touches_bottom = geo.bottom() >= mw_h - edge
            touches_top    = geo.top()    <= edge

            child_left_global   = mw_tl.x() + geo.left()
            child_right_global  = mw_tl.x() + geo.right()
            child_top_global    = mw_tl.y() + geo.top()
            child_bottom_global = mw_tl.y() + geo.bottom()

            if touches_right and not spans_w and spans_h:
                rect.setRight(min(rect.right(), child_left_global - 1))
            elif touches_left and not spans_w and spans_h:
                rect.setLeft(max(rect.left(), child_right_global + 1))
            elif touches_bottom and not spans_h and spans_w:
                rect.setBottom(min(rect.bottom(), child_top_global - 1))
            elif touches_top and not spans_h and spans_w:
                rect.setTop(max(rect.top(), child_bottom_global + 1))

        return rect

    def _natural_left_top(self) -> tuple[int, int]:
        """Natural (x, y) for the overlay's top-left corner with no user offset.

        Anchored on the LEFT EDGE so collapse (right side disappears) and
        expand (right side reappears) never shift the chevron or the left edge.
        We use the last-known EXPANDED size so the anchor is identical whether
        the bar is currently collapsed or expanded.
        """
        margin = 16
        rect = self._viewport_rect_global()
        ref_w = self._last_expanded_size.width()  if self._last_expanded_size else self.width()
        ref_h = self._last_expanded_size.height() if self._last_expanded_size else self.height()
        return (
            rect.right()  - ref_w - margin,
            rect.bottom() - ref_h - margin,
        )

    def _compute_natural_position(self) -> QPoint:
        x, y = self._natural_left_top()
        return QPoint(x, y)

    def _reposition(self) -> None:
        """Move the overlay so its left edge stays fixed; only the right edge grows/shrinks."""
        layout = self.layout()
        if layout:
            layout.activate()
        self.adjustSize()

        nat_x, nat_y = self._natural_left_top()
        self.move(
            nat_x + self._user_offset[0],
            nat_y + self._user_offset[1],
        )

        # Update _last_expanded_size only when flagged (deferred call from _rebuild),
        # NEVER in the synchronous call — writing a partial size there would corrupt
        # the reference and shift the bar rightward on the deferred correction.
        if self._needs_size_update and not self._collapsed:
            self._last_expanded_size = QtCore.QSize(self.size())
            self._needs_size_update = False

    # ------------------------------------------------------------------
    # Button management
    # ------------------------------------------------------------------

    def _rebuild(self) -> None:
        # Remove old widgets from grid (chevron and add_btn are kept alive)
        for btn in self._buttons.values():
            self._layout.removeWidget(btn)
            btn.deleteLater()
        self._buttons.clear()
        self._layout.removeWidget(self._add_btn)
        self._layout.removeWidget(self._collapse_btn)
        self._add_btn.hide()

        if not project.is_open():
            self._should_be_visible = False
            self.hide()
            return

        if self._collapsed:
            # Only the chevron is shown
            self._layout.addWidget(self._collapse_btn, 0, 0)
            self._collapse_btn.show()
        else:
            try:
                stack = textureset.get_active_stack()
                channels = stack.all_channels()
            except Exception:
                self._should_be_visible = False
                self.hide()
                return

            ch_types = list(channels.keys())
            total = len(ch_types)
            # Channels start at column 1 (column 0 is the chevron)
            if total <= _MAX_PER_ROW:
                for col, ch_type in enumerate(ch_types):
                    btn = self._make_channel_button(ch_type)
                    self._layout.addWidget(btn, 0, col + 1)
                    self._buttons[ch_type] = btn
                self._layout.addWidget(self._add_btn, 0, total + 1)
                nb_rows = 1
            else:
                for idx, ch_type in enumerate(ch_types):
                    btn = self._make_channel_button(ch_type)
                    row = idx // _MAX_PER_ROW
                    col = (idx % _MAX_PER_ROW) + 1
                    self._layout.addWidget(btn, row, col)
                    self._buttons[ch_type] = btn
                add_row = total // _MAX_PER_ROW
                add_col = (total % _MAX_PER_ROW) + 1
                self._layout.addWidget(self._add_btn, add_row, add_col)
                nb_rows = add_row + 1

            # Chevron spans all rows so it's centered vertically
            self._layout.addWidget(self._collapse_btn, 0, 0, nb_rows, 1)
            self._collapse_btn.show()
            self._add_btn.show()

        self._should_be_visible = True
        app = QtWidgets.QApplication.instance()
        if app is None or app.applicationState() == Qt.ApplicationActive:
            self.show()
        self._refresh_states()
        if not self._collapsed:
            # Flag: the deferred call (after layout settles) will update _last_expanded_size.
            # The synchronous call below must NOT write it to avoid corrupting the reference.
            self._needs_size_update = True
        self._reposition()
        QTimer.singleShot(0, self._reposition)

    def _toggle_collapse(self) -> None:
        self._collapsed = not self._collapsed
        self._update_collapse_btn()
        s = vg_settings.load_settings()
        s["channel_overlay_collapsed"] = self._collapsed
        vg_settings.save_settings(s)
        # _rebuild → _reposition takes care of placement; since we anchor on the
        # chevron, it stays put regardless of bar size.
        self._rebuild()

    def _update_collapse_btn(self) -> None:
        self._collapse_btn.setText("›" if self._collapsed else "‹")
        action = "Expand" if self._collapsed else "Collapse"
        self._collapse_btn.setToolTip(
            f"{action} channel bar  •  Drag to move  •  Right-click for options"
        )

    def _make_channel_button(self, ch_type: ChannelType) -> QtWidgets.QPushButton:
        label = _CHANNEL_LABELS.get(ch_type.name, ch_type.name)
        color = _CHANNEL_COLORS.get(ch_type.name, "#808080")
        btn = QtWidgets.QPushButton(label)
        btn.setCheckable(True)
        btn.setStyleSheet(self._theme.channel_btn_style(color))
        btn.setToolTip(ch_type.name)
        btn.setMaximumWidth(110)
        btn.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)
        btn.clicked.connect(lambda checked, ct=ch_type: self._toggle_channel(ct))
        btn.setContextMenuPolicy(Qt.CustomContextMenu)
        btn.customContextMenuRequested.connect(lambda pos, ct=ch_type: self._show_remove_menu(ct))
        return btn

    @staticmethod
    def _read_active_channels(node):
        """Return the node's active_channels as a set, or None if unsupported."""
        try:
            return set(node.active_channels)
        except Exception:
            return None

    @staticmethod
    def _can_write_channels(node) -> bool:
        """True only for node types that support the active_channels setter.

        Uses class name comparison to avoid import fragility.
        The API only documents the setter on FillLayerNode / FillEffectNode.
        """
        return type(node).__name__ in ("FillLayerNode", "FillEffectNode")

    @staticmethod
    def _write_active_channels(node, channels: set) -> bool:
        """Assign active_channels; True on success, False if the node rejects it."""
        try:
            node.active_channels = channels
            return True
        except Exception:
            return False

    @staticmethod
    def _node_key(node) -> object:
        """Stable identifier for a node across selections."""
        for attr in ("uid", "id"):
            try:
                v = getattr(node, attr, None)
                if v is not None and not callable(v):
                    return (attr, v)
            except Exception:
                pass
        try:
            v = node.uid()  # method form, just in case
            return ("uid_call", v)
        except Exception:
            pass
        return ("py_id", id(node))

    def _save_source(self, node, ch_type: ChannelType) -> None:
        """Cache what is needed to restore the channel's content after active_channels write.

        active_channels reassignment resets all sources even for channels that
        were already active. We snapshot each source type in the form that
        set_source() can accept back:
          - SourceUniformColor → Color value
          - SourceBitmap       → resource_id (ResourceID — stable, lives in the project)
          - others             → source object itself (best effort)
        """
        try:
            src = node.get_source(ch_type)
        except Exception:
            return
        if src is None:
            return
        key = (self._node_key(node), ch_type)
        src_class = type(src).__name__
        try:
            if src_class == "SourceUniformColor":
                self._source_cache[key] = ("color", src.get_color())
                return
            if src_class == "SourceBitmap":
                # resource_id is a ResourceID — survives active_channels changes
                self._source_cache[key] = ("resource_id", src.resource_id)
                return
        except Exception:
            pass
        # Generic fallback for SourceSubstance, SourceVectorial, SourceFont, …
        self._source_cache[key] = ("source", src)

    def _restore_source(self, node, ch_type: ChannelType) -> None:
        """Re-apply the cached content after the channel has been re-added."""
        key = (self._node_key(node), ch_type)
        entry = self._source_cache.get(key)
        if entry is None:
            return
        kind, value = entry
        try:
            # All three forms are accepted by set_source(): Color, ResourceID, or source object
            node.set_source(ch_type, value)
        except Exception:
            pass

    def _native_channel_button_states(self) -> dict:
        """Scan Painter's Properties panel and return {ChannelType: bool checked}."""
        my_btns = set(self._buttons.values()) | {self._add_btn, self._collapse_btn}
        _ABBREVS: dict[str, ChannelType] = {}
        _extra = {
            "color": "BaseColor", "rough": "Roughness", "metal": "Metallic",
            "nrm": "Normal", "height": "Height", "ao": "AO",
            "scatt": "Scattering", "emissive": "Emissive", "opac": "Opacity",
            "opacity": "Opacity", "specular": "Specular", "gloss": "Glossiness",
            "displace": "Displacement",
        }
        for abbrev, ch_name in _extra.items():
            ct = getattr(ChannelType, ch_name, None)
            if ct is not None:
                _ABBREVS[abbrev] = ct
        for ch_name, label in _CHANNEL_LABELS.items():
            ct = getattr(ChannelType, ch_name, None)
            if ct is not None:
                for tok in [ch_name.lower(), label.lower(), label.lower().replace(" ", "")]:
                    _ABBREVS.setdefault(tok, ct)

        result: dict = {}
        for btn in self._main_window.findChildren(QtWidgets.QAbstractButton):
            if btn in my_btns or not btn.isVisible() or not btn.isCheckable():
                continue
            text = btn.text().strip()
            if len(text) > 12:
                continue
            for raw in (btn.text(), btn.toolTip()):
                if not raw:
                    continue
                tok = raw.strip().lower()
                ct = _ABBREVS.get(tok)
                if ct is None:
                    first = tok.split()[0].split("—")[0].split("(")[0].strip()
                    ct = _ABBREVS.get(first)
                if ct is not None:
                    result[ct] = btn.isChecked()
                    break
        return result

    def _refresh_states(self) -> None:
        if not project.is_open():
            return

        # Re-show if the overlay was hidden by a transient focus loss
        if self._should_be_visible and not self.isVisible():
            app = QtWidgets.QApplication.instance()
            if app is None or app.applicationState() == Qt.ApplicationActive:
                self.show()
                self._reposition()

        self.setWindowOpacity(1.0)

        # Primary source of truth: native Properties panel buttons.
        # They reflect the actual channel state for both Fill and Paint layers.
        native_states = self._native_channel_button_states()

        # Fallback: read active_channels from selected nodes (Fill layers only)
        fallback_active = set()
        if not native_states:
            try:
                stack = textureset.get_active_stack()
                selected = layerstack.get_selected_nodes(stack)
                node_channels = []
                for node in selected:
                    chs = self._read_active_channels(node)
                    if chs is not None:
                        node_channels.append(chs)
                if node_channels:
                    fallback_active = set.intersection(*node_channels) if len(node_channels) > 1 else node_channels[0]
            except Exception:
                pass

        for ch_type, btn in self._buttons.items():
            if native_states:
                state = native_states.get(ch_type, False)
            else:
                state = ch_type in fallback_active
            btn.blockSignals(True)
            btn.setChecked(state)
            btn.blockSignals(False)
            btn.setToolTip(ch_type.name)

    # ------------------------------------------------------------------
    # Interactions
    # ------------------------------------------------------------------

    def _toggle_channel(self, ch_type: ChannelType) -> None:
        if not project.is_open():
            return
        try:
            stack = textureset.get_active_stack()
            selected = layerstack.get_selected_nodes(stack)
        except Exception:
            self._refresh_states()
            return

        if not selected:
            self._refresh_states()
            return

        # Try the native Properties panel button FIRST — works for both Fill and
        # Paint layers regardless of whether active_channels is readable from Python.
        if self._click_native_properties_button(ch_type):
            QTimer.singleShot(50, self._refresh_states)
            return

        # Fallback: active_channels API (Fill layers only)
        writable_targets = []
        for node in selected:
            if not self._can_write_channels(node):
                continue
            chs = self._read_active_channels(node)
            if chs is not None:
                writable_targets.append((node, chs))
        if not writable_targets:
            self._refresh_states()
            return

        all_active = all(ch_type in chs for _, chs in writable_targets)
        for node, chs in writable_targets:
            new_chs = set(chs)
            for ch in chs:
                self._save_source(node, ch)
            if all_active:
                new_chs.discard(ch_type)
            else:
                new_chs.add(ch_type)
            self._write_active_channels(node, new_chs)
            for ch in new_chs:
                self._restore_source(node, ch)

        self._refresh_states()

    def _click_native_properties_button(self, ch_type: ChannelType) -> bool:
        """Find and click the matching channel button in Painter's Properties panel.

        Painter's UI puts each channel toggle in its own parent widget, so a
        group/fingerprint match is impossible. Instead we rely on the unique
        abbreviation mapping (color → BaseColor, rough → Roughness, …) and
        click the first visible button that matches the requested channel.
        """
        my_btns = set(self._buttons.values()) | {self._add_btn, self._collapse_btn}

        # Abbreviation table — covers Painter's Properties-panel labels
        _ABBREVS: dict[str, ChannelType] = {}
        _extra = {
            "color": "BaseColor", "rough": "Roughness", "metal": "Metallic",
            "nrm": "Normal", "height": "Height", "ao": "AO",
            "scatt": "Scattering", "emissive": "Emissive", "opac": "Opacity",
            "opacity": "Opacity", "specular": "Specular", "gloss": "Glossiness",
            "displace": "Displacement",
        }
        for abbrev, ch_name in _extra.items():
            ct = getattr(ChannelType, ch_name, None)
            if ct is not None:
                _ABBREVS[abbrev] = ct
        for ch_name, label in _CHANNEL_LABELS.items():
            ct = getattr(ChannelType, ch_name, None)
            if ct is not None:
                for tok in [ch_name.lower(), label.lower(), label.lower().replace(" ", "")]:
                    _ABBREVS.setdefault(tok, ct)

        def _btn_channel(btn) -> ChannelType | None:
            for raw in (btn.text(), btn.toolTip()):
                if not raw:
                    continue
                tok = raw.strip().lower()
                if tok in _ABBREVS:
                    return _ABBREVS[tok]
                first = tok.split()[0].split("—")[0].split("(")[0].strip()
                if first in _ABBREVS:
                    return _ABBREVS[first]
            return None

        # Find every checkable, visible button (any QAbstractButton subclass)
        # outside our own bar that maps to the requested channel.
        candidates = []
        for btn in self._main_window.findChildren(QtWidgets.QAbstractButton):
            if btn in my_btns or not btn.isVisible() or not btn.isCheckable():
                continue
            text = btn.text().strip()
            if len(text) > 12:
                continue
            if _btn_channel(btn) == ch_type:
                candidates.append(btn)

        if not candidates:
            try:
                import substance_painter.logging as sp_logging
                sp_logging.info(
                    f"VG Channel Overlay: no native button found for {ch_type.name}"
                )
            except Exception:
                pass
            return False

        # Click the first match — Painter's per-layer Properties panel only ever
        # shows one button per channel, so ambiguity is extremely unlikely.
        candidates[0].click()
        return True

    def _show_remove_menu(self, ch_type: ChannelType) -> None:
        label = _CHANNEL_LABELS.get(ch_type.name, ch_type.name)
        menu = QtWidgets.QMenu(self)
        action = menu.addAction(f"Remove '{label}' from Texture Set")
        action.triggered.connect(lambda: self._remove_channel(ch_type))
        menu.exec(QtGui.QCursor.pos())

    def _remove_channel(self, ch_type: ChannelType) -> None:
        if not project.is_open():
            return
        label = _CHANNEL_LABELS.get(ch_type.name, ch_type.name)
        reply = QtWidgets.QMessageBox.question(
            self,
            "Remove Channel",
            f"You are about to delete the <b>{label}</b> channel.<br><br>"
            "This will affect all layers in the Texture Set. Are you sure?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel,
            QtWidgets.QMessageBox.Cancel,
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return
        try:
            stack = textureset.get_active_stack()
            stack.remove_channel(ch_type)
        except Exception:
            pass
        self._rebuild()

    def _show_add_menu(self) -> None:
        if not project.is_open():
            return
        try:
            stack = textureset.get_active_stack()
            existing = set(stack.all_channels().keys())
        except Exception:
            return

        missing = [ct for ct in _ALL_CHANNEL_TYPES if ct not in existing]
        if not missing:
            return

        menu = QtWidgets.QMenu(self)
        for ct in missing:
            label = _CHANNEL_LABELS.get(ct.name, ct.name)
            action = menu.addAction(label)
            action.triggered.connect(lambda checked, c=ct: self._add_channel(c))
        menu.exec(QtGui.QCursor.pos())

    def _add_channel(self, ch_type: ChannelType) -> None:
        if not project.is_open():
            return
        try:
            stack = textureset.get_active_stack()
            fmt = _DEFAULT_FORMAT.get(ch_type.name, ChannelFormat.L8)
            stack.add_channel(ch_type, fmt)
        except Exception:
            pass
        self._rebuild()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        try:
            self._selection_timer.stop()
        except Exception:
            pass
        for ev, cb in [
            (sp_event.LayerStacksModelDataChanged, self._on_stack_changed),
            (sp_event.ProjectOpened, self._on_project_opened),
            (sp_event.ProjectAboutToClose, self._on_project_closed),
        ]:
            try:
                event.DISPATCHER.disconnect(ev, cb)
            except Exception:
                pass
        try:
            if self._main_window:
                self._main_window.removeEventFilter(self)
                central = (
                    self._main_window.centralWidget()
                    if hasattr(self._main_window, "centralWidget")
                    else None
                )
                if central is not None:
                    central.removeEventFilter(self)
        except Exception:
            pass
        try:
            app = QtWidgets.QApplication.instance()
            if app is not None:
                app.applicationStateChanged.disconnect(self._on_app_state_changed)
        except Exception:
            pass

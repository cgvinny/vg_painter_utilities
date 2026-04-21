##########################################################################
#
# Copyright 2010-2024 Vincent GAULT - Adobe
# All Rights Reserved.
#
##########################################################################

"""
Extracts a color palette from fill layers with an active Base Color channel
in the active texture set, and displays it in a dockable panel.
"""
__author__ = "Vincent GAULT - Adobe"

from substance_painter import textureset, layerstack, colormanagement, project, logging, event
from substance_painter import source as sp_source
from PySide6 import QtWidgets, QtGui, QtCore

_BASE_COLOR = textureset.ChannelType.BaseColor
_SRGB = colormanagement.GenericColorSpace.sRGB

_COLOR_KEYWORDS = ("color", "colour", "tint", "hue", "albedo", "diffuse", "base")


# ─── Color helpers ───────────────────────────────────────────────────────────

def _sp_to_qcolor(sp_color):
    try:
        srgb = sp_color.sRGB
        return QtGui.QColor.fromRgbF(
            max(0.0, min(1.0, float(srgb[0]))),
            max(0.0, min(1.0, float(srgb[1]))),
            max(0.0, min(1.0, float(srgb[2]))),
        )
    except Exception:
        return QtGui.QColor(128, 128, 128)


def _qcolor_to_sp(qc):
    return colormanagement.Color(qc.redF(), qc.greenF(), qc.blueF(), _SRGB)


# ─── Source extraction / application ─────────────────────────────────────────

def _extract_all_from_source(src):
    """Return a list of (QColor, substance_param_key) for all color params found."""
    results = []
    try:
        if isinstance(src, sp_source.SourceUniformColor):
            return [(_sp_to_qcolor(src.get_color()), None)]

        if isinstance(src, sp_source.SourceSubstance):
            params = src.get_parameters()

            # Pass 1: any parameter typed as colormanagement.Color, regardless of name
            for key, val in params.items():
                if isinstance(val, colormanagement.Color):
                    results.append((_sp_to_qcolor(val), key))

            # Pass 2: tuple/list (3-4 floats) with a color-related name
            for key, val in params.items():
                if isinstance(val, (list, tuple)) and 3 <= len(val) <= 4:
                    if any(w in key.lower() for w in _COLOR_KEYWORDS):
                        try:
                            results.append((QtGui.QColor.fromRgbF(
                                max(0.0, min(1.0, float(val[0]))),
                                max(0.0, min(1.0, float(val[1]))),
                                max(0.0, min(1.0, float(val[2]))),
                            ), key))
                        except Exception:
                            pass

            if not results and params:
                sample = {k: f"{type(v).__name__}({repr(v)[:30]})"
                          for k, v in list(params.items())[:6]}
                logging.info(f"VG Palette: no color found — params: {sample}")

    except Exception as e:
        logging.warning(f"VG Palette: could not extract color from source: {e}")
    return results


def _extract_from_source(src):
    """Return (QColor, substance_param_key) for the first color found, or (None, None)."""
    results = _extract_all_from_source(src)
    return results[0] if results else (None, None)


def _apply_color(src, new_qcolor, substance_key):
    """Write new_qcolor back to src immediately."""
    if isinstance(src, sp_source.SourceUniformColor):
        src.set_color(_qcolor_to_sp(new_qcolor))
    elif isinstance(src, sp_source.SourceSubstance) and substance_key:
        try:
            params = src.get_parameters()
            updated = dict(params)
            if isinstance(params.get(substance_key), colormanagement.Color):
                updated[substance_key] = _qcolor_to_sp(new_qcolor)
            else:
                updated[substance_key] = [new_qcolor.redF(), new_qcolor.greenF(), new_qcolor.blueF()]
            src.set_parameters(updated)
        except Exception as e:
            logging.error(f"VG Palette: set_parameters failed: {e}")


# ─── Stack walking ────────────────────────────────────────────────────────────

def _walk(nodes, out, ignore_hidden):
    for node in nodes:
        try:
            if ignore_hidden and not node.is_visible():
                continue

            try:
                children = node.sub_layers()
                if children:
                    _walk(children, out, ignore_hidden)
            except Exception:
                pass

            if node.get_type() != layerstack.NodeType.FillLayer:
                continue

            if _BASE_COLOR not in node.active_channels:
                continue

            try:
                if node.source_mode == sp_source.SourceMode.Material:
                    src = node.get_material_source()
                else:
                    src = node.get_source(_BASE_COLOR)
            except Exception as e:
                logging.warning(f"VG Palette: get_source failed on '{node.get_name()}': {e}")
                continue

            colors = _extract_all_from_source(src)
            if colors:
                node_name = node.get_name()
                if len(colors) == 1:
                    out.append((node, node_name, colors[0][0], src, colors[0][1]))
                else:
                    for qcolor, sub_key in colors:
                        label = f"{node_name} — {sub_key}"
                        out.append((node, label, qcolor, src, sub_key))
            else:
                logging.info(
                    f"VG Palette: '{node.get_name()}' skipped — "
                    f"BaseColor source type '{type(src).__name__}' not supported"
                )
        except Exception as e:
            logging.warning(f"VG Palette: error processing node: {e}")


def collect(stack, ignore_hidden=True):
    out = []
    _walk(layerstack.get_root_layer_nodes(stack), out, ignore_hidden)
    return out


def _hue_distance(h1, h2):
    """Return the shortest angular distance between two hues in [0, 1]."""
    diff = abs(h1 - h2)
    return min(diff, 1.0 - diff)


def find_similar_hue_layers(reference_color, tolerance_pct, all_ts, ignore_hidden,
                             exclude_srcs=None):
    """
    Scan texture sets for fill layers whose Base Color hue is within
    *tolerance_pct* (0-100) of *reference_color*.

    Returns a list of (ts_name, node, display_name, qcolor, src, sub_key).
    Entries whose src id() is in *exclude_srcs* are skipped.
    """
    exclude_srcs = exclude_srcs or set()
    ref_h = reference_color.hsvHueF()
    if ref_h < 0:  # achromatic reference — nothing to match on hue
        return []
    tolerance = tolerance_pct / 100.0

    texture_sets = textureset.all_texture_sets() if all_ts else [
        textureset.get_active_stack().material()
    ]

    results = []
    for ts in texture_sets:
        try:
            stack = ts.get_stack()
            entries = collect(stack, ignore_hidden)
            for node, name, qcolor, src, sub_key in entries:
                if id(src) in exclude_srcs:
                    continue
                h = qcolor.hsvHueF()
                if h < 0:
                    continue
                if _hue_distance(ref_h, h) <= tolerance:
                    results.append((ts.name, node, name, qcolor, src, sub_key))
        except Exception as e:
            logging.warning(f"VG Palette: error scanning '{ts.name}': {e}")
    return results


# ─── UI helpers ──────────────────────────────────────────────────────────────

_COLOR_MIME_TYPE = "application/x-vg-palette-color"


def _apply_hue_only(picked, current):
    """Return a color with the hue of *picked* and the S+V of *current*."""
    h = picked.hsvHueF()
    if h < 0:  # picked is achromatic — use as-is
        return picked
    return QtGui.QColor.fromHsvF(h, current.hsvSaturationF(), current.valueF())


class _DraggableSwatch(QtWidgets.QPushButton):
    """Swatch button that initiates a color drag on mouse move."""

    def __init__(self, qcolor, parent=None):
        super().__init__(parent)
        self._color = qcolor
        self._drag_start = None

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_start = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (event.buttons() & QtCore.Qt.LeftButton
                and self._drag_start is not None
                and (event.pos() - self._drag_start).manhattanLength()
                    > QtWidgets.QApplication.startDragDistance()):
            drag = QtGui.QDrag(self)
            mime = QtCore.QMimeData()
            mime.setData(_COLOR_MIME_TYPE, self._color.name().encode())
            drag.setMimeData(mime)
            pix = QtGui.QPixmap(24, 24)
            pix.fill(self._color)
            drag.setPixmap(pix)
            drag.exec(QtCore.Qt.CopyAction)
            self._drag_start = None
        super().mouseMoveEvent(event)


class _DropTargetSwatch(QtWidgets.QPushButton):
    """Swatch button that accepts a color drop."""
    color_dropped = QtCore.Signal(QtGui.QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(_COLOR_MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasFormat(_COLOR_MIME_TYPE):
            color = QtGui.QColor(bytes(event.mimeData().data(_COLOR_MIME_TYPE)).decode())
            if color.isValid():
                self.color_dropped.emit(color)
                event.acceptProposedAction()


# ─── UI ──────────────────────────────────────────────────────────────────────

class _FlowLayout(QtWidgets.QLayout):
    """A layout that wraps its children like words in a paragraph."""

    def __init__(self, parent=None, spacing=4):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return QtCore.Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QtCore.QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QtCore.QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return size + QtCore.QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do_layout(self, rect, test_only):
        m = self.contentsMargins()
        x = rect.x() + m.left()
        y = rect.y() + m.top()
        line_h = 0
        right = rect.right() - m.right()
        for item in self._items:
            hint = item.sizeHint()
            iw, ih = hint.width(), hint.height()
            next_x = x + iw + self._spacing
            if next_x > right and line_h > 0:
                x = rect.x() + m.left()
                y += line_h + self._spacing
                next_x = x + iw + self._spacing
                line_h = 0
            if not test_only:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), hint))
            x = next_x
            line_h = max(line_h, ih)
        return y + line_h - rect.y() + m.bottom()


class _PropagateConfirmDialog(QtWidgets.QDialog):
    """
    Shows layers with a similar hue grouped by Texture Set.
    User can deselect individual entries before applying.
    """

    def __init__(self, matches, new_color, preserve_sv_fn, parent=None):
        """
        matches: list of (ts_name, node, display_name, qcolor, src, sub_key)
        new_color: the color to apply (raw, before any hue-only transform)
        preserve_sv_fn: callable returning bool (hue-only option)
        """
        super().__init__(parent)
        self.setWindowTitle("Propagate Color Change")
        self.setMinimumWidth(360)

        self._new_color = new_color
        self._preserve_sv_fn = preserve_sv_fn
        self._checkboxes = []  # list of (cb, src, sub_key, current_qcolor)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(8)

        total = len(matches)
        layout.addWidget(QtWidgets.QLabel(
            f"<b>{total} layer{'s' if total != 1 else ''}</b> with a similar hue found. "
            f"Select which ones to update:"
        ))

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setMaximumHeight(300)

        inner = QtWidgets.QWidget()
        inner_layout = QtWidgets.QVBoxLayout(inner)
        inner_layout.setSpacing(2)
        inner_layout.setContentsMargins(0, 0, 0, 0)

        # Group by texture set
        groups = {}
        for ts_name, node, name, qcolor, src, sub_key in matches:
            groups.setdefault(ts_name, []).append((node, name, qcolor, src, sub_key))

        for ts_name, entries in groups.items():
            lbl = QtWidgets.QLabel(f"<b>{ts_name}</b>")
            lbl.setStyleSheet("color: #aaa; margin-top: 4px;")
            inner_layout.addWidget(lbl)
            for node, name, qcolor, src, sub_key in entries:
                row = QtWidgets.QHBoxLayout()
                cb = QtWidgets.QCheckBox(name)
                cb.setChecked(True)

                swatch = QtWidgets.QLabel()
                swatch.setFixedSize(20, 14)
                pix = QtGui.QPixmap(20, 14)
                pix.fill(qcolor)
                swatch.setPixmap(pix)

                arrow = QtWidgets.QLabel("→")
                arrow.setStyleSheet("color: #888;")

                preview = QtWidgets.QLabel()
                preview.setFixedSize(20, 14)
                preview_color = (
                    _apply_hue_only(new_color, qcolor) if preserve_sv_fn() else new_color
                )
                ppix = QtGui.QPixmap(20, 14)
                ppix.fill(preview_color)
                preview.setPixmap(ppix)

                row.addWidget(cb, 1)
                row.addWidget(swatch)
                row.addWidget(arrow)
                row.addWidget(preview)
                inner_layout.addLayout(row)
                self._checkboxes.append((cb, src, sub_key, qcolor))

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        # Select all / none
        sel_row = QtWidgets.QHBoxLayout()
        sel_all = QtWidgets.QPushButton("Select All")
        sel_none = QtWidgets.QPushButton("Select None")
        sel_all.setFlat(True)
        sel_none.setFlat(True)
        sel_all.clicked.connect(lambda: self._set_all(True))
        sel_none.clicked.connect(lambda: self._set_all(False))
        sel_row.addWidget(sel_all)
        sel_row.addWidget(sel_none)
        sel_row.addStretch()
        layout.addLayout(sel_row)

        btn_row = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Cancel | QtWidgets.QDialogButtonBox.Apply
        )
        btn_row.rejected.connect(self.reject)
        btn_row.button(QtWidgets.QDialogButtonBox.Apply).clicked.connect(self._apply)
        layout.addWidget(btn_row)

    def _set_all(self, state):
        for cb, *_ in self._checkboxes:
            cb.setChecked(state)

    def _apply(self):
        preserve = self._preserve_sv_fn()
        for cb, src, sub_key, current_qcolor in self._checkboxes:
            if not cb.isChecked():
                continue
            color = (_apply_hue_only(self._new_color, current_qcolor)
                     if preserve else self._new_color)
            try:
                _apply_color(src, color, sub_key)
            except Exception as e:
                logging.error(f"VG Palette: propagate failed: {e}")
        self.accept()


def _make_remove_btn():
    btn = QtWidgets.QPushButton("×")
    btn.setFlat(True)
    btn.setFixedSize(16, 16)
    btn.setToolTip("Remove from list (removes all checked rows)")
    btn.setStyleSheet(
        "QPushButton { border: none; color: #888; font-size: 13px; padding: 0; "
        "min-width: 16px; max-width: 16px; min-height: 16px; max-height: 16px; }"
        "QPushButton:hover { color: #ddd; }"
    )
    return btn


class _ColorRow(QtWidgets.QWidget):
    removed = QtCore.Signal(object)
    color_applied = QtCore.Signal(QtGui.QColor, str)       # (new_color, name)
    color_changed = QtCore.Signal(QtGui.QColor, QtGui.QColor, object)  # (original, new, src)

    _FRAME_NORMAL  = "QFrame { border: 1px solid #555; border-radius: 4px; }"
    _FRAME_CHECKED = "QFrame { border: 2px solid #3a8fd1; border-radius: 4px; }"

    def __init__(self, node, name, qcolor, src, sub_key,
                 preserve_sv_fn=None, get_checked_fn=None, parent=None):
        super().__init__(parent)
        self._node = node
        self._src = src
        self._sub_key = sub_key
        self._color = qcolor
        self._preserve_sv_fn = preserve_sv_fn or (lambda: False)
        self._get_checked_fn = get_checked_fn or (lambda: [])

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(6)

        self._checkbox = QtWidgets.QCheckBox()
        self._checkbox.setToolTip("Select for batch operations")
        self._checkbox.stateChanged.connect(self._update_frame_style)
        layout.addWidget(self._checkbox)

        self._swatch = _DropTargetSwatch()
        self._swatch.setFixedSize(34, 34)
        self._swatch.setStyleSheet(
            "QPushButton { border: none; padding: 0; margin: 0; "
            "min-width: 34px; max-width: 34px; min-height: 34px; max-height: 34px; }"
        )
        self._swatch.setCursor(QtCore.Qt.PointingHandCursor)
        self._swatch.setToolTip("Click to change color — drag a swatch here to apply it")
        self._update_swatch(qcolor)
        self._swatch.clicked.connect(self._pick_color)
        self._swatch.color_dropped.connect(lambda c: self._apply_new_color(c, add_to_history=False))
        layout.addWidget(self._swatch)

        self._name_frame = QtWidgets.QFrame()
        self._name_frame.setStyleSheet(self._FRAME_NORMAL)
        frame_layout = QtWidgets.QHBoxLayout(self._name_frame)
        frame_layout.setContentsMargins(6, 0, 4, 0)
        frame_layout.setSpacing(0)

        self._name_btn = QtWidgets.QPushButton(name)
        self._name_btn.setFlat(True)
        self._name_btn.setStyleSheet("text-align: left; padding: 0; border: none;")
        self._name_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._name_btn.setToolTip("Click to select this layer in the stack")
        self._name_btn.clicked.connect(self._select_layer)
        frame_layout.addWidget(self._name_btn, 1)

        rm_btn = _make_remove_btn()
        rm_btn.clicked.connect(lambda: self.removed.emit(self))
        frame_layout.addWidget(rm_btn)

        layout.addWidget(self._name_frame, 1)

    def _update_frame_style(self, state):
        self._name_frame.setStyleSheet(
            self._FRAME_CHECKED if state else self._FRAME_NORMAL
        )

    def _update_swatch(self, qcolor):
        pix = QtGui.QPixmap(32, 32)
        pix.fill(qcolor)
        self._swatch.setIcon(QtGui.QIcon(pix))
        self._swatch.setIconSize(QtCore.QSize(32, 32))

    def _apply_new_color(self, new_color, add_to_history=True, _cascade=True, _propagate=True):
        original = self._color
        raw = new_color  # pass raw color to siblings so each applies its own hue transform
        if self._preserve_sv_fn():
            new_color = _apply_hue_only(new_color, self._color)
        self._color = new_color
        self._update_swatch(new_color)
        try:
            _apply_color(self._src, new_color, self._sub_key)
            if add_to_history:
                self.color_applied.emit(new_color, self._node.get_name())
            if _propagate:
                self.color_changed.emit(original, raw, self._src)
        except Exception as e:
            logging.error(f"VG Palette: could not update layer color: {e}")
        if _cascade:
            for row in self._get_checked_fn():
                if row is not self:
                    row._apply_new_color(raw, add_to_history=False, _cascade=False, _propagate=False)

    def _pick_color(self):
        new_color = QtWidgets.QColorDialog.getColor(
            self._color, self, "Pick Color",
            QtWidgets.QColorDialog.DontUseNativeDialog,
        )
        if not new_color.isValid():
            return
        self._apply_new_color(new_color)

    def _select_layer(self):
        try:
            layerstack.set_selected_nodes([self._node])
        except Exception as e:
            logging.error(f"VG Palette: could not select layer: {e}")


class _MergedColorRow(QtWidgets.QWidget):
    """A row representing multiple fill layers that share the same color."""
    removed = QtCore.Signal(object)
    color_applied = QtCore.Signal(QtGui.QColor, str)
    color_changed = QtCore.Signal(QtGui.QColor, QtGui.QColor, object)  # (original, new, src)

    _FRAME_NORMAL  = "QFrame { border: 1px solid #555; border-radius: 4px; }"
    _FRAME_CHECKED = "QFrame { border: 2px solid #3a8fd1; border-radius: 4px; }"

    def __init__(self, entries, preserve_sv_fn=None, get_checked_fn=None, parent=None):
        super().__init__(parent)
        # entries: list of (node, name, qcolor, src, sub_key)
        self._entries = entries
        self._color = entries[0][2]
        self._preserve_sv_fn = preserve_sv_fn or (lambda: False)
        self._get_checked_fn = get_checked_fn or (lambda: [])

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(6)

        self._checkbox = QtWidgets.QCheckBox()
        self._checkbox.setToolTip("Select for batch operations")
        self._checkbox.stateChanged.connect(self._update_frame_style)
        layout.addWidget(self._checkbox)

        self._swatch = _DropTargetSwatch()
        self._swatch.setFixedSize(34, 34)
        self._swatch.setStyleSheet(
            "QPushButton { border: none; padding: 0; margin: 0; "
            "min-width: 34px; max-width: 34px; min-height: 34px; max-height: 34px; }"
        )
        self._swatch.setCursor(QtCore.Qt.PointingHandCursor)
        self._swatch.setToolTip("Click to change color for all layers — drag a swatch here to apply it")
        self._update_swatch(self._color)
        self._swatch.clicked.connect(self._pick_color)
        self._swatch.color_dropped.connect(lambda c: self._apply_new_color(c, add_to_history=False))
        layout.addWidget(self._swatch)

        self._name_frame = QtWidgets.QFrame()
        self._name_frame.setStyleSheet(self._FRAME_NORMAL)
        frame_layout = QtWidgets.QHBoxLayout(self._name_frame)
        frame_layout.setContentsMargins(6, 0, 4, 0)
        frame_layout.setSpacing(0)

        names = [e[1] for e in entries]
        label = ", ".join(names) if len(names) <= 2 else f"{names[0]} (+{len(names) - 1} more)"
        name_lbl = QtWidgets.QPushButton(label)
        name_lbl.setFlat(True)
        name_lbl.setStyleSheet("text-align: left; padding: 0; border: none;")
        name_lbl.setCursor(QtCore.Qt.PointingHandCursor)
        name_lbl.setToolTip(f"Layers sharing this color:\n{chr(10).join(names)}\n\nClick to select all")
        name_lbl.clicked.connect(self._select_layers)
        frame_layout.addWidget(name_lbl, 1)

        rm_btn = _make_remove_btn()
        rm_btn.clicked.connect(lambda: self.removed.emit(self))
        frame_layout.addWidget(rm_btn)

        layout.addWidget(self._name_frame, 1)

    def _update_frame_style(self, state):
        self._name_frame.setStyleSheet(
            self._FRAME_CHECKED if state else self._FRAME_NORMAL
        )

    def _update_swatch(self, qcolor):
        pix = QtGui.QPixmap(32, 32)
        pix.fill(qcolor)
        self._swatch.setIcon(QtGui.QIcon(pix))
        self._swatch.setIconSize(QtCore.QSize(32, 32))

    def _apply_new_color(self, new_color, add_to_history=True, _cascade=True, _propagate=True):
        original = self._color
        raw = new_color
        if self._preserve_sv_fn():
            new_color = _apply_hue_only(new_color, self._color)
        self._color = new_color
        self._update_swatch(new_color)
        names = []
        for node, name, _, src, sub_key in self._entries:
            try:
                _apply_color(src, new_color, sub_key)
                names.append(name)
            except Exception as e:
                logging.error(f"VG Palette: could not update '{name}': {e}")
        if names and add_to_history:
            self.color_applied.emit(new_color, ", ".join(names))
        if _propagate and names:
            self.color_changed.emit(original, raw, self._entries[0][3])
        if _cascade:
            for row in self._get_checked_fn():
                if row is not self:
                    row._apply_new_color(raw, add_to_history=False, _cascade=False, _propagate=False)

    def _pick_color(self):
        new_color = QtWidgets.QColorDialog.getColor(
            self._color, self, "Pick Color",
            QtWidgets.QColorDialog.DontUseNativeDialog,
        )
        if not new_color.isValid():
            return
        self._apply_new_color(new_color)

    def _select_layers(self):
        try:
            layerstack.set_selected_nodes([e[0] for e in self._entries])
        except Exception as e:
            logging.error(f"VG Palette: could not select layers: {e}")


class PalettePanel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Base Color Manager")
        self.setMinimumWidth(280)

        self._active_stack_name = None
        self._connect_events()

        from PySide6.QtCore import QTimer
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(500)
        self._poll_timer.timeout.connect(self._check_active_stack)
        self._poll_timer.start()

        root = QtWidgets.QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(8, 8, 8, 8)

        # ── Header ───────────────────────────────────────────────────────────
        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Fill Layer Colors — Base Color")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        header.addWidget(title)
        header.addStretch()
        refresh_btn = QtWidgets.QPushButton("↺")
        refresh_btn.setFlat(True)
        refresh_btn.setFixedSize(22, 22)
        refresh_btn.setStyleSheet(
            "QPushButton { border: none; font-size: 18px; color: #aaa; padding: 0; "
            "min-width: 22px; max-width: 22px; min-height: 22px; max-height: 22px; }"
            "QPushButton:hover { color: #fff; }"
        )
        refresh_btn.setToolTip("Refresh list from current stack")
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn)
        root.addLayout(header)

        # ── Options (vertical) ───────────────────────────────────────────────
        self._ignore_hidden_cb = QtWidgets.QCheckBox("Ignore hidden layers")
        self._ignore_hidden_cb.setChecked(True)
        self._ignore_hidden_cb.stateChanged.connect(lambda _: self.refresh())
        root.addWidget(self._ignore_hidden_cb)

        self._merge_cb = QtWidgets.QCheckBox("Merge identical colors")
        self._merge_cb.setChecked(True)
        self._merge_cb.stateChanged.connect(lambda _: self.refresh())
        root.addWidget(self._merge_cb)

        self._hue_only_cb = QtWidgets.QCheckBox("Hue only")
        self._hue_only_cb.setChecked(True)
        self._hue_only_cb.setToolTip(
            "When changing or dropping a color, preserve the layer's\n"
            "original Saturation and Brightness — only the Hue changes."
        )
        root.addWidget(self._hue_only_cb)

        propagate_row = QtWidgets.QHBoxLayout()
        self._propagate_cb = QtWidgets.QCheckBox("Propagate similar hues:")
        self._propagate_cb.setChecked(False)
        self._propagate_cb.setToolTip(
            "After a color change, scan for layers with a similar hue\n"
            "and offer to apply the same change to them."
        )
        self._propagate_cb.stateChanged.connect(self._on_propagate_toggled)

        self._tolerance_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self._tolerance_slider.setRange(1, 30)
        self._tolerance_slider.setValue(5)
        self._tolerance_slider.setEnabled(False)

        self._tolerance_lbl = QtWidgets.QLabel("5%")
        self._tolerance_lbl.setFixedWidth(30)
        self._tolerance_lbl.setEnabled(False)
        self._tolerance_slider.valueChanged.connect(
            lambda v: self._tolerance_lbl.setText(f"{v}%")
        )

        propagate_row.addWidget(self._propagate_cb)
        propagate_row.addWidget(self._tolerance_slider, 1)
        propagate_row.addWidget(self._tolerance_lbl)
        root.addLayout(propagate_row)

        self._propagate_all_ts_cb = QtWidgets.QCheckBox("All Texture Sets")
        self._propagate_all_ts_cb.setChecked(True)
        self._propagate_all_ts_cb.setEnabled(False)
        self._propagate_all_ts_cb.setToolTip(
            "When propagating, search all Texture Sets.\n"
            "When unchecked, only the active Texture Set is scanned."
        )
        root.addWidget(self._propagate_all_ts_cb)

        # ── "Layers" section label with separator ────────────────────────────
        layers_header = QtWidgets.QHBoxLayout()
        layers_lbl = QtWidgets.QLabel("Layers")
        layers_lbl.setStyleSheet("color: #888; font-size: 11px;")
        sep_line = QtWidgets.QFrame()
        sep_line.setFrameShape(QtWidgets.QFrame.HLine)
        sep_line.setFrameShadow(QtWidgets.QFrame.Sunken)
        layers_header.addWidget(layers_lbl)
        layers_header.addWidget(sep_line, 1)
        root.addLayout(layers_header)

        # ── Layer rows scroll area ────────────────────────────────────────────
        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

        self._container = QtWidgets.QWidget()
        self._rows_layout = QtWidgets.QVBoxLayout(self._container)
        self._rows_layout.setSpacing(4)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.addStretch()
        self._scroll.setWidget(self._container)
        root.addWidget(self._scroll)

        # ── Applied colors grid ───────────────────────────────────────────────
        swatch_header = QtWidgets.QHBoxLayout()
        swatch_lbl = QtWidgets.QLabel("Applied colors")
        swatch_lbl.setStyleSheet("color: #888; font-size: 11px;")
        swatch_header.addWidget(swatch_lbl)
        swatch_header.addStretch()
        clear_btn = QtWidgets.QPushButton("Clear")
        clear_btn.setFixedHeight(22)
        clear_btn.setStyleSheet(
            "QPushButton { border: 1px solid #555; border-radius: 4px; padding: 0 8px; }"
            "QPushButton:hover { border-color: #888; }"
        )
        clear_btn.setToolTip("Clear color history")
        clear_btn.clicked.connect(self._clear_swatches)
        swatch_header.addWidget(clear_btn)
        root.addLayout(swatch_header)

        swatch_scroll = QtWidgets.QScrollArea()
        swatch_scroll.setWidgetResizable(True)
        swatch_scroll.setMaximumHeight(200)
        swatch_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        swatch_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        swatch_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        self._swatch_container = QtWidgets.QWidget()
        self._swatch_layout = _FlowLayout(self._swatch_container, spacing=4)
        self._swatch_container.setLayout(self._swatch_layout)
        swatch_scroll.setWidget(self._swatch_container)
        root.addWidget(swatch_scroll)

        self.refresh()

    def _connect_events(self):
        event.DISPATCHER.connect_strong(event.LayerStacksModelDataChanged, self._on_stack_model_changed)
        event.DISPATCHER.connect_strong(event.ProjectOpened, self._on_project_event)
        event.DISPATCHER.connect_strong(event.ProjectClosed, self._on_project_event)

    def _disconnect_events(self):
        try:
            event.DISPATCHER.disconnect(event.LayerStacksModelDataChanged, self._on_stack_model_changed)
            event.DISPATCHER.disconnect(event.ProjectOpened, self._on_project_event)
            event.DISPATCHER.disconnect(event.ProjectClosed, self._on_project_event)
        except Exception:
            pass

    def closeEvent(self, e):
        self._poll_timer.stop()
        self._disconnect_events()
        super().closeEvent(e)

    def _active_ts_name(self):
        """Return the active texture set name, or None if unavailable."""
        try:
            return textureset.get_active_stack().material().name
        except Exception:
            return None

    def _on_stack_model_changed(self, e):
        name = self._active_ts_name()
        if name and name != self._active_stack_name:
            self.refresh()

    def _check_active_stack(self):
        """Timer fallback: catches texture set switches that don't emit LayerStacksModelDataChanged."""
        if not project.is_open():
            if self._active_stack_name is not None:
                self._active_stack_name = None
                self.refresh()
            return
        name = self._active_ts_name()
        if name and name != self._active_stack_name:
            self.refresh()

    def _on_project_event(self, e):
        self.refresh()

    def _on_propagate_toggled(self, state):
        enabled = bool(state)
        self._tolerance_slider.setEnabled(enabled)
        self._tolerance_lbl.setEnabled(enabled)
        self._propagate_all_ts_cb.setEnabled(enabled)

    def _maybe_propagate(self, original_color, new_color, source_src):
        if not self._propagate_cb.isChecked():
            return
        if not project.is_open():
            return
        tolerance_pct = self._tolerance_slider.value()
        all_ts = self._propagate_all_ts_cb.isChecked()
        ignore_hidden = self._ignore_hidden_cb.isChecked()
        matches = find_similar_hue_layers(
            original_color, tolerance_pct, all_ts, ignore_hidden,
            exclude_srcs={id(source_src)}
        )
        if not matches:
            return
        dlg = _PropagateConfirmDialog(
            matches, new_color,
            preserve_sv_fn=lambda: self._hue_only_cb.isChecked(),
            parent=self,
        )
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            self.refresh()

    def _clear_rows(self):
        while self._rows_layout.count() > 1:
            item = self._rows_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def refresh(self):
        self._clear_rows()

        if not project.is_open():
            self._active_stack_name = None
            self._add_info("No project open.")
            return

        stack = textureset.get_active_stack()
        self._active_stack_name = stack.material().name
        entries = collect(stack, ignore_hidden=self._ignore_hidden_cb.isChecked())

        if not entries:
            self._add_info("No fill layers with Base Color found.")
            return

        rows = self._build_rows(entries)
        for i, row in enumerate(rows):
            row.removed.connect(self._remove_row)
            row.color_applied.connect(self._add_to_swatches)
            row.color_changed.connect(self._maybe_propagate)
            self._rows_layout.insertWidget(i, row)

    def _get_checked_rows(self):
        rows = []
        for i in range(self._rows_layout.count() - 1):  # -1 to skip trailing stretch
            item = self._rows_layout.itemAt(i)
            if item:
                w = item.widget()
                if w and hasattr(w, '_checkbox') and w._checkbox.isChecked():
                    rows.append(w)
        return rows

    def _build_rows(self, entries):
        preserve_sv = lambda: self._hue_only_cb.isChecked()
        get_checked = self._get_checked_rows
        if not self._merge_cb.isChecked():
            return [_ColorRow(n, name, c, s, k, preserve_sv, get_checked)
                    for n, name, c, s, k in entries]
        groups = {}
        for entry in entries:
            key = entry[2].name()  # hex string — exact 8-bit match
            groups.setdefault(key, []).append(entry)
        rows = []
        for group in groups.values():
            if len(group) == 1:
                n, name, c, s, k = group[0]
                rows.append(_ColorRow(n, name, c, s, k, preserve_sv, get_checked))
            else:
                rows.append(_MergedColorRow(group, preserve_sv, get_checked))
        return rows

    def _add_info(self, text):
        lbl = QtWidgets.QLabel(text)
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        self._rows_layout.insertWidget(0, lbl)

    def _remove_row(self, row_widget):
        to_remove = set(self._get_checked_rows())
        to_remove.add(row_widget)
        for row in to_remove:
            self._rows_layout.removeWidget(row)
            row.deleteLater()

    def _add_to_swatches(self, qcolor, layer_name):
        btn = _DraggableSwatch(qcolor)
        btn.setFixedSize(26, 26)
        btn.setCursor(QtCore.Qt.PointingHandCursor)
        pix = QtGui.QPixmap(24, 24)
        pix.fill(qcolor)
        btn.setIcon(QtGui.QIcon(pix))
        btn.setIconSize(QtCore.QSize(24, 24))
        btn.setStyleSheet(
            "QPushButton { border: none; padding: 0; margin: 0; "
            "min-width: 26px; max-width: 26px; min-height: 26px; max-height: 26px; }"
        )
        btn.setToolTip(f"{layer_name}\n{qcolor.name().upper()}\nClick to apply to selection — drag to a row swatch")
        btn.clicked.connect(lambda: self._apply_swatch_to_selection(qcolor))
        self._swatch_layout.addWidget(btn)
        self._swatch_container.updateGeometry()

    def _clear_swatches(self):
        while self._swatch_layout.count():
            item = self._swatch_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _apply_swatch_to_selection(self, qcolor):
        if not project.is_open():
            return
        stack = textureset.get_active_stack()
        hue_only = self._hue_only_cb.isChecked()
        for node in layerstack.get_selected_nodes(stack):
            if node.get_type() != layerstack.NodeType.FillLayer:
                continue
            if _BASE_COLOR not in node.active_channels:
                continue
            try:
                if node.source_mode == sp_source.SourceMode.Material:
                    src = node.get_material_source()
                else:
                    src = node.get_source(_BASE_COLOR)
                current_color, sub_key = _extract_from_source(src)
                color_to_apply = qcolor
                if hue_only and current_color is not None:
                    color_to_apply = _apply_hue_only(qcolor, current_color)
                _apply_color(src, color_to_apply, sub_key)
            except Exception as e:
                logging.warning(f"VG Palette: could not apply swatch: {e}")

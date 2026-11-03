##########################################################################
#
# Copyright 2010-2024 Vincent GAULT - Adobe
# All Rights Reserved.
#
##########################################################################

"""
Extracts a color palette from fill layers with an active Base Color channel
across all texture sets, groups identical or similar colors, and displays it in
a dockable panel with snapshots and relative saturation/lightness adjustment.
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


def collect_all(ignore_hidden=True):
    """
    Scan every texture set. Returns (node, display_name, qcolor, src, sub_key, ts) tuples;
    the display name is prefixed with the texture set name when there are several.
    """
    out = []
    texture_sets = textureset.all_texture_sets()
    multi = len(texture_sets) > 1
    for ts in texture_sets:
        try:
            for node, name, qcolor, src, sub_key in collect(ts.get_stack(), ignore_hidden):
                out.append((node, f"{ts.name} / {name}" if multi else name, qcolor, src, sub_key, ts))
        except Exception as e:
            logging.warning(f"VG Palette: error scanning '{ts.name}': {e}")
    return out


def _lab(qcolor):
    """sRGB QColor → CIE Lab (D65), for perceptual distance."""
    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = lin(qcolor.redF()), lin(qcolor.greenF()), lin(qcolor.blueF())
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def _delta_e(lab1, lab2):
    return sum((a - b) ** 2 for a, b in zip(lab1, lab2)) ** 0.5


def _hue_sort_key(qcolor):
    """Sort key: chromatic colors by hue then lightness, grays last by lightness."""
    h = qcolor.hsvHueF()
    if h < 0 or qcolor.hsvSaturationF() < 0.08:
        return (1, 0.0, qcolor.lightnessF())
    return (0, h, qcolor.lightnessF())


def group_entries(entries, tolerance):
    """
    Group entries by color. *tolerance* is a Lab distance (ΔE); 0 groups exact 8-bit
    matches only. Each group is led by its first member, in scan order.
    """
    if tolerance <= 0:
        groups = {}
        for entry in entries:
            groups.setdefault(entry[2].name(), []).append(entry)
        return list(groups.values())

    groups = []  # list of (leader_lab, members)
    for entry in entries:
        lab = _lab(entry[2])
        for leader_lab, members in groups:
            if _delta_e(leader_lab, lab) <= tolerance:
                members.append(entry)
                break
        else:
            groups.append((lab, [entry]))
    return [members for _, members in groups]


# ─── UI helpers ──────────────────────────────────────────────────────────────

_COLOR_MIME_TYPE = "application/x-vg-palette-color"


_MODE_HUE = "hue"
_MODE_HUE_SAT = "hue_sat"


def _apply_hue_only(picked, current, mode=_MODE_HUE):
    """
    Return a color with the hue of *picked* and the value of *current*.
    Saturation comes from *current* ("hue") or from *picked* ("hue_sat").
    """
    h = picked.hsvHueF()
    if h < 0:  # picked is achromatic — use as-is
        return picked
    s = picked.hsvSaturationF() if mode == _MODE_HUE_SAT else current.hsvSaturationF()
    return QtGui.QColor.fromHsvF(h, s, current.valueF())


def _offset_color(base, d_sat, d_light):
    """
    Return *base* shifted by relative offsets in [-1, 1] on HSL saturation and lightness.
    Positive moves toward the maximum by that fraction of the remaining headroom,
    negative scales toward zero, so results never clip and 0 is the identity.
    Hue is untouched; achromatic colors stay achromatic on saturation.
    """
    h = base.hslHueF()
    s = base.hslSaturationF()
    l = base.lightnessF()

    def shift(v, d):
        return v + (1.0 - v) * d if d >= 0 else v * (1.0 + d)

    new_s = shift(s, d_sat) if h >= 0 else s
    new_l = shift(l, d_light)
    return QtGui.QColor.fromHslF(max(h, 0.0), new_s, new_l)


# ─── Snapshots (stored in the project file) ──────────────────────────────────

_META_CONTEXT = "vg_base_color_manager"
_META_KEY = "snapshots"
DEFAULT_SNAPSHOT = "Default"
BACKUP_SNAPSHOT = "Before restore (auto)"


def _node_uid(node):
    try:
        return node.uid()
    except Exception:
        return None


def load_snapshots():
    """Return the project's snapshots dict, or None if none were ever stored."""
    try:
        meta = project.Metadata(_META_CONTEXT)
        if _META_KEY not in meta.list():
            return None
        return meta.get(_META_KEY) or {}
    except Exception as e:
        logging.warning(f"VG Palette: could not read snapshots: {e}")
        return None


def _store_snapshots(snapshots):
    project.Metadata(_META_CONTEXT).set(_META_KEY, snapshots)


def take_snapshot():
    """Return a serializable record of every Base Color of every texture set."""
    entries = []
    for ts in textureset.all_texture_sets():
        try:
            counts = {}
            for node, name, qcolor, _src, sub_key in collect(ts.get_stack(), ignore_hidden=False):
                occ_key = (name, sub_key)
                occ = counts.get(occ_key, 0)
                counts[occ_key] = occ + 1
                entries.append({
                    "ts": ts.name, "uid": _node_uid(node), "name": name,
                    "key": sub_key or "", "occ": occ,
                    "rgb": [qcolor.redF(), qcolor.greenF(), qcolor.blueF()],
                })
        except Exception as e:
            logging.warning(f"VG Palette: snapshot skipped '{ts.name}': {e}")
    return {"entries": entries}


def save_snapshot(name):
    snapshots = load_snapshots() or {}
    snapshots[name] = take_snapshot()
    _store_snapshots(snapshots)
    return len(snapshots[name]["entries"])


def delete_snapshot(name):
    snapshots = load_snapshots() or {}
    if snapshots.pop(name, None) is not None:
        _store_snapshots(snapshots)


def ensure_default_snapshot():
    """Create the 'Default' snapshot the first time a project is seen. Returns True if created."""
    if not project.is_open() or load_snapshots() is not None:
        return False
    try:
        save_snapshot(DEFAULT_SNAPSHOT)
        return True
    except Exception as e:
        logging.warning(f"VG Palette: could not create default snapshot: {e}")
        return False


def restore_snapshot(name):
    """
    Write a snapshot's colors back to the layers. Layers are matched by uid, then by
    (texture set, name, sub-key, occurrence). Returns (restored, missing).
    """
    snap = (load_snapshots() or {}).get(name)
    if snap is None:
        return 0, 0

    current = {}  # ts name -> (by_uid, by_name)
    for ts in textureset.all_texture_sets():
        by_uid, by_name, counts = {}, {}, {}
        for node, nname, qcolor, src, sub_key in collect(ts.get_stack(), ignore_hidden=False):
            occ = counts.get((nname, sub_key), 0)
            counts[(nname, sub_key)] = occ + 1
            row = (src, sub_key)
            uid = _node_uid(node)
            if uid is not None:
                by_uid[(uid, sub_key or "")] = row
            by_name[(nname, sub_key or "", occ)] = row
        current[ts.name] = (by_uid, by_name)

    restored = missing = 0
    for e in snap["entries"]:
        by_uid, by_name = current.get(e["ts"], ({}, {}))
        target = by_uid.get((e["uid"], e["key"])) or by_name.get((e["name"], e["key"], e["occ"]))
        if target is None:
            missing += 1
            continue
        r, g, b = e["rgb"]
        try:
            _apply_color(target[0], QtGui.QColor.fromRgbF(r, g, b), target[1])
            restored += 1
        except Exception as ex:
            logging.warning(f"VG Palette: restore failed on '{e['name']}': {ex}")
            missing += 1
    return restored, missing


_SPECTRUM_BUTTON_QSS = {
    # Spectrum dark theme, medium size: 32px tall, fully rounded, sentence case.
    "accent": (
        "QPushButton { background: #3B63FB; color: #FFFFFF; border: 2px solid #3B63FB; }"
        "QPushButton:hover { background: #274DEA; border-color: #274DEA; }"
        "QPushButton:pressed { background: #1D3FC9; border-color: #1D3FC9; }"
        "QPushButton:disabled { background: transparent; color: #6D6D6D; border-color: #4B4B4B; }"
    ),
    "secondary": (
        "QPushButton { background: transparent; color: #E3E3E3; border: 2px solid #8F8F8F; }"
        "QPushButton:hover { background: rgba(255,255,255,0.10); border-color: #B1B1B1; }"
        "QPushButton:pressed { background: rgba(255,255,255,0.18); }"
        "QPushButton:disabled { color: #6D6D6D; border-color: #4B4B4B; }"
    ),
    "quiet": (
        "QPushButton { background: transparent; color: #E3E3E3; border: 2px solid transparent; }"
        "QPushButton:hover { background: rgba(255,255,255,0.10); }"
        "QPushButton:pressed { background: rgba(255,255,255,0.18); }"
        "QPushButton:disabled { color: #6D6D6D; }"
    ),
}


def _spectrum_button(text, variant="secondary", tooltip=""):
    """Pill button following Adobe Spectrum; stretches to share the row evenly."""
    btn = QtWidgets.QPushButton(text)
    btn.setFixedHeight(32)
    btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
    btn.setMinimumWidth(24)  # lets the button shrink with the panel instead of overflowing
    btn.setCursor(QtCore.Qt.PointingHandCursor)
    btn.setStyleSheet(
        _SPECTRUM_BUTTON_QSS[variant]
        + "QPushButton { border-radius: 16px; padding: 0 8px; font-weight: bold; }"
    )
    if tooltip:
        btn.setToolTip(tooltip)
    return btn


def _draw_icon(kind, color="#FFFFFF", size=16):
    """Small line icon ('add', 'restore', 'delete') drawn in code, so no resource files are needed."""
    pix = QtGui.QPixmap(size, size)
    pix.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pix)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    pen = QtGui.QPen(QtGui.QColor(color), 1.6)
    pen.setCapStyle(QtCore.Qt.RoundCap)
    pen.setJoinStyle(QtCore.Qt.RoundJoin)
    p.setPen(pen)
    s = size
    if kind == "add":
        p.drawLine(QtCore.QPointF(s / 2, 3), QtCore.QPointF(s / 2, s - 3))
        p.drawLine(QtCore.QPointF(3, s / 2), QtCore.QPointF(s - 3, s / 2))
    elif kind == "restore":
        rect = QtCore.QRectF(3, 3, s - 6, s - 6)
        p.drawArc(rect, 40 * 16, 280 * 16)       # open circle, gap at the top-right
        p.drawLine(QtCore.QPointF(s - 3, 2.5), QtCore.QPointF(s - 3, 6.5))   # arrow head
        p.drawLine(QtCore.QPointF(s - 3, 6.5), QtCore.QPointF(s - 7, 6.5))
    elif kind == "link":
        # two interlocked rounded links, tilted
        p.translate(s / 2, s / 2)
        p.rotate(-45)
        p.drawRoundedRect(QtCore.QRectF(-s * 0.42, -s * 0.16, s * 0.52, s * 0.32), s * 0.16, s * 0.16)
        p.drawRoundedRect(QtCore.QRectF(-s * 0.10, -s * 0.16, s * 0.52, s * 0.32), s * 0.16, s * 0.16)
    elif kind == "eyedropper":
        p.drawLine(QtCore.QPointF(3, s - 3), QtCore.QPointF(7, s - 7))        # tip
        thick = QtGui.QPen(QtGui.QColor(color), 3.2)
        thick.setCapStyle(QtCore.Qt.RoundCap)
        p.setPen(thick)
        p.drawLine(QtCore.QPointF(7.5, s - 7.5), QtCore.QPointF(s - 6, 6))    # body
        p.setPen(pen)
        p.drawEllipse(QtCore.QPointF(s - 4.5, 4.5), 2.2, 2.2)                  # bulb
    elif kind == "delete":
        p.drawLine(QtCore.QPointF(3, 4.5), QtCore.QPointF(s - 3, 4.5))        # lid
        p.drawLine(QtCore.QPointF(6, 4.5), QtCore.QPointF(6, 2.5))
        p.drawLine(QtCore.QPointF(6, 2.5), QtCore.QPointF(s - 6, 2.5))
        p.drawLine(QtCore.QPointF(s - 6, 2.5), QtCore.QPointF(s - 6, 4.5))
        p.drawRect(QtCore.QRectF(4.5, 4.5, s - 9, s - 7.5))                   # bin
    p.end()
    return QtGui.QIcon(pix)


def _spectrum_icon_button(kind, variant, tooltip):
    """Round 32px icon-only button; the tooltip carries the label."""
    btn = QtWidgets.QPushButton()
    btn.setFixedSize(32, 32)
    btn.setCursor(QtCore.Qt.PointingHandCursor)
    btn.setStyleSheet(_SPECTRUM_BUTTON_QSS[variant] + "QPushButton { border-radius: 16px; padding: 0; }")
    btn.setIcon(_draw_icon(kind, "#FFFFFF" if variant == "accent" else "#E3E3E3"))
    btn.setIconSize(QtCore.QSize(16, 16))
    btn.setToolTip(tooltip)
    return btn


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


def _clamp01(x):
    return max(0.0, min(1.0, x))


class _SVSquare(QtWidgets.QWidget):
    """Saturation (x) / value (y) square for the current hue."""
    changed = QtCore.Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._h, self._s, self._v = 0.0, 0.0, 1.0
        self.setMinimumSize(220, 150)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.setCursor(QtCore.Qt.CrossCursor)

    def set_state(self, h, s, v):
        self._h, self._s, self._v = h, s, v
        self.update()

    def _area(self):
        return QtCore.QRectF(self.rect()).adjusted(8, 8, -8, -8)

    def paintEvent(self, _event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        r = self._area()
        clip = QtGui.QPainterPath()
        clip.addRoundedRect(r, 6, 6)
        p.setClipPath(clip)
        horizontal = QtGui.QLinearGradient(r.left(), 0, r.right(), 0)
        horizontal.setColorAt(0, QtGui.QColor(255, 255, 255))
        horizontal.setColorAt(1, QtGui.QColor.fromHsvF(self._h, 1.0, 1.0))
        p.fillRect(r, horizontal)
        vertical = QtGui.QLinearGradient(0, r.top(), 0, r.bottom())
        vertical.setColorAt(0, QtGui.QColor(0, 0, 0, 0))
        vertical.setColorAt(1, QtGui.QColor(0, 0, 0, 255))
        p.fillRect(r, vertical)
        p.setClipping(False)
        c = QtCore.QPointF(r.left() + self._s * r.width(), r.top() + (1.0 - self._v) * r.height())
        p.setBrush(QtCore.Qt.NoBrush)
        p.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 160), 3))
        p.drawEllipse(c, 7, 7)
        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 2))
        p.drawEllipse(c, 7, 7)

    def _pick(self, pos):
        r = self._area()
        self._s = _clamp01((pos.x() - r.left()) / r.width())
        self._v = 1.0 - _clamp01((pos.y() - r.top()) / r.height())
        self.update()
        self.changed.emit(self._s, self._v)

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self._pick(e.position())

    def mouseMoveEvent(self, e):
        if e.buttons() & QtCore.Qt.LeftButton:
            self._pick(e.position())


class _HueBar(QtWidgets.QWidget):
    """Horizontal rainbow slider."""
    changed = QtCore.Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._h = 0.0
        self.setFixedHeight(26)
        self.setCursor(QtCore.Qt.PointingHandCursor)

    def set_hue(self, h):
        self._h = h
        self.update()

    def _area(self):
        return QtCore.QRectF(self.rect()).adjusted(8, 5, -8, -5)

    def paintEvent(self, _event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        r = self._area()
        grad = QtGui.QLinearGradient(r.left(), 0, r.right(), 0)
        for i in range(7):
            grad.setColorAt(i / 6.0, QtGui.QColor.fromHsvF(i / 6.0, 1.0, 1.0))
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(grad)
        p.drawRoundedRect(r, 8, 8)
        c = QtCore.QPointF(r.left() + self._h * r.width(), r.center().y())
        p.setBrush(QtCore.Qt.NoBrush)
        p.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 160), 3))
        p.drawEllipse(c, 8, 8)
        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 2))
        p.drawEllipse(c, 8, 8)

    def _pick(self, pos):
        r = self._area()
        self._h = _clamp01((pos.x() - r.left()) / r.width())
        self.update()
        self.changed.emit(self._h)

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self._pick(e.position())

    def mouseMoveEvent(self, e):
        if e.buttons() & QtCore.Qt.LeftButton:
            self._pick(e.position())


class _BeforeAfterBar(QtWidgets.QWidget):
    """Left half: color when the picker opened. Right half: current color."""

    def __init__(self, before, parent=None):
        super().__init__(parent)
        self._before = QtGui.QColor(before)
        self._after = QtGui.QColor(before)
        self.setFixedHeight(32)
        self.setToolTip("Left: original — Right: new")

    def set_color(self, color):
        self._after = QtGui.QColor(color)
        self.update()

    def paintEvent(self, _event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        r = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        clip = QtGui.QPainterPath()
        clip.addRoundedRect(r, 6, 6)
        p.setClipPath(clip)
        half = r.width() / 2
        p.fillRect(QtCore.QRectF(r.left(), r.top(), half, r.height()), self._before)
        p.fillRect(QtCore.QRectF(r.left() + half, r.top(), half, r.height()), self._after)


class _ColorPickerDialog(QtWidgets.QDialog):
    """
    Compact HSV color picker. Emits currentColorChanged while the user drags,
    so callers can apply the color live; drop-in for the bits of QColorDialog we used.
    """
    currentColorChanged = QtCore.Signal(QtGui.QColor)
    modeChanged = QtCore.Signal(object)   # False, "hue" or "hue_sat"

    def __init__(self, color, mode=_MODE_HUE, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pick Color")
        self._h = max(color.hsvHueF(), 0.0)
        self._s = color.hsvSaturationF()
        self._v = color.valueF()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._sv = _SVSquare()
        self._sv.changed.connect(self._on_sv)
        layout.addWidget(self._sv, 1)

        self._hue = _HueBar()
        self._hue.changed.connect(self._on_hue)
        layout.addWidget(self._hue)

        self._bar = _BeforeAfterBar(color)
        layout.addWidget(self._bar)

        self._hex = QtWidgets.QLineEdit()
        self._hex.setFixedHeight(32)
        self._hex.setMaxLength(7)
        self._hex.setPlaceholderText("#RRGGBB")
        self._hex.textEdited.connect(self._on_hex)

        self._picking = False
        self._before_pick = None
        self._pick_timer = QtCore.QTimer(self)
        self._pick_timer.setInterval(30)
        self._pick_timer.timeout.connect(self._sample_screen)
        eye_btn = _spectrum_icon_button(
            "eyedropper", "secondary",
            "Pick a color from anywhere on the screen — inside or outside Painter.\n"
            "Click to confirm the sample, Esc to cancel.")
        eye_btn.clicked.connect(self._start_eyedropper)

        # One compact row: [format] [value fields] [eyedropper]. HEX is shown by default.
        def spin(prefix, maximum, tip):
            sb = QtWidgets.QSpinBox()
            sb.setRange(0, maximum)
            sb.setPrefix(prefix)
            sb.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
            sb.setFixedHeight(32)
            sb.setToolTip(tip)
            sb.setMinimumWidth(40)
            return sb

        self._rgb = [spin("R ", 255, "Red 0–255"), spin("G ", 255, "Green 0–255"),
                     spin("B ", 255, "Blue 0–255")]
        self._hsv = [spin("H ", 359, "Hue 0–359°"), spin("S ", 100, "Saturation 0–100%"),
                     spin("V ", 100, "Value (brightness) 0–100%")]
        for sb in self._rgb:
            sb.valueChanged.connect(self._on_rgb)
        for sb in self._hsv:
            sb.valueChanged.connect(self._on_hsv)

        def spin_page(spins):
            page = QtWidgets.QWidget()
            row = QtWidgets.QHBoxLayout(page)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
            for sb in spins:
                row.addWidget(sb, 1)
            return page

        self._value_stack = QtWidgets.QStackedWidget()
        self._value_stack.addWidget(self._hex)
        self._value_stack.addWidget(spin_page(self._rgb))
        self._value_stack.addWidget(spin_page(self._hsv))

        self._format_combo = QtWidgets.QComboBox()
        self._format_combo.addItems(["HEX", "RGB", "HSV"])
        self._format_combo.setFixedSize(66, 32)
        self._format_combo.setToolTip("Type the color as HEX, RGB (0–255) or HSV")
        self._format_combo.currentIndexChanged.connect(self._value_stack.setCurrentIndex)

        value_row = QtWidgets.QHBoxLayout()
        value_row.setSpacing(6)
        value_row.addWidget(self._format_combo)
        value_row.addWidget(self._value_stack, 1)
        value_row.addWidget(eye_btn)
        layout.addLayout(value_row)

        mode_row = QtWidgets.QHBoxLayout()
        mode_lbl = QtWidgets.QLabel("Apply")
        mode_lbl.setFixedWidth(40)
        self._mode_combo = _WideCombo()
        self._mode_combo.setFixedHeight(32)
        self._mode_combo.setToolTip(
            "Full color: the layers take exactly this color.\n"
            "Hue only: they take its hue and keep their own saturation and brightness.\n"
            "Hue + saturation: they keep only their own brightness."
        )
        for text, m in (("Full color", False),
                        ("Hue only", _MODE_HUE),
                        ("Hue + saturation", _MODE_HUE_SAT)):
            self._mode_combo.addItem(text, m)
        self._mode_combo.setCurrentIndex(max(0, self._mode_combo.findData(mode or False)))
        self._mode_combo.currentIndexChanged.connect(self._on_mode)
        mode_row.addWidget(mode_lbl)
        mode_row.addWidget(self._mode_combo, 1)
        layout.addLayout(mode_row)

        buttons = QtWidgets.QHBoxLayout()
        buttons.setSpacing(6)
        cancel = _spectrum_button("Cancel", "secondary")
        cancel.clicked.connect(self.reject)
        ok = _spectrum_button("OK", "accent")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        buttons.addWidget(cancel, 1)
        buttons.addWidget(ok, 1)
        layout.addLayout(buttons)

        self._refresh_widgets()

    def currentColor(self):
        return QtGui.QColor.fromHsvF(self._h, self._s, self._v)

    def mode(self):
        return self._mode_combo.currentData()

    def _on_mode(self, _index):
        self.modeChanged.emit(self.mode())
        self.currentColorChanged.emit(self.currentColor())  # re-apply with the new mode

    def _refresh_widgets(self, skip_hex=False):
        color = self.currentColor()
        self._sv.set_state(self._h, self._s, self._v)
        self._hue.set_hue(self._h)
        self._bar.set_color(color)
        if not skip_hex:
            self._hex.setText(color.name().upper())
        # keep the numeric fields in sync without re-triggering their handlers
        values = ((self._rgb, (color.red(), color.green(), color.blue())),
                  (self._hsv, (round(self._h * 360) % 360, round(self._s * 100), round(self._v * 100))))
        for spins, vals in values:
            for sb, val in zip(spins, vals):
                if sb.value() != val:
                    sb.blockSignals(True)
                    sb.setValue(val)
                    sb.blockSignals(False)

    def _notify(self):
        self._refresh_widgets()
        self.currentColorChanged.emit(self.currentColor())

    def _on_sv(self, s, v):
        self._s, self._v = s, v
        self._notify()

    def _on_hue(self, h):
        self._h = h
        self._notify()

    def _set_from_qcolor(self, c, skip_hex=False):
        if c.hsvHueF() >= 0:  # keep the current hue when the color is gray
            self._h = c.hsvHueF()
        self._s, self._v = c.hsvSaturationF(), c.valueF()
        self._refresh_widgets(skip_hex=skip_hex)
        self.currentColorChanged.emit(self.currentColor())

    def _on_hex(self, text):
        digits = text.lstrip("#")
        if len(digits) not in (3, 6):
            return
        c = QtGui.QColor("#" + digits)
        if c.isValid():
            self._set_from_qcolor(c, skip_hex=True)

    def _on_rgb(self, _value):
        c = QtGui.QColor(*(sb.value() for sb in self._rgb))
        self._set_from_qcolor(c)

    def _on_hsv(self, _value):
        h, s, v = (sb.value() for sb in self._hsv)
        self._h, self._s, self._v = h / 360.0, s / 100.0, v / 100.0
        self._refresh_widgets()
        self.currentColorChanged.emit(self.currentColor())

    # ── Screen eyedropper ────────────────────────────────────────────────────

    def _start_eyedropper(self):
        """Follow the cursor anywhere on screen; a click keeps the sample, Esc cancels."""
        if self._picking:
            return
        self._picking = True
        self._before_pick = (self._h, self._s, self._v)
        QtGui.QGuiApplication.setOverrideCursor(QtCore.Qt.CrossCursor)
        self.grabMouse()      # also receives clicks that land outside the window
        self.grabKeyboard()
        self._pick_timer.start()
        self._sample_screen()

    def _stop_eyedropper(self, keep):
        if not self._picking:
            return
        self._picking = False
        self._pick_timer.stop()
        self.releaseMouse()
        self.releaseKeyboard()
        QtGui.QGuiApplication.restoreOverrideCursor()
        if not keep and self._before_pick:
            self._h, self._s, self._v = self._before_pick
            self._refresh_widgets()
            self.currentColorChanged.emit(self.currentColor())

    def _sample_screen(self):
        pos = QtGui.QCursor.pos()
        screen = QtGui.QGuiApplication.screenAt(pos) or QtGui.QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.geometry()
        image = screen.grabWindow(0, pos.x() - geo.x(), pos.y() - geo.y(), 1, 1).toImage()
        if image.isNull():
            return
        self._set_from_qcolor(image.pixelColor(0, 0))

    def mousePressEvent(self, e):
        if self._picking:
            self._sample_screen()
            self._stop_eyedropper(keep=True)
            return
        super().mousePressEvent(e)

    def keyPressEvent(self, e):
        if self._picking:
            if e.key() == QtCore.Qt.Key_Escape:
                self._stop_eyedropper(keep=False)
            return
        super().keyPressEvent(e)

    def done(self, result):
        self._stop_eyedropper(keep=True)
        super().done(result)


class _ColorRow(QtWidgets.QWidget):
    """
    A row for one group of fill layers (a single layer, identical colors, or
    similar colors). Every member keeps its own color: with a hue-only mode,
    each one takes the new hue while preserving its own saturation/brightness.
    """
    removed = QtCore.Signal(object)
    color_applied = QtCore.Signal(QtGui.QColor, str)       # (new_color, name)

    _FRAME_NORMAL  = "QFrame { border: 1px solid #555; border-radius: 4px; }"
    _FRAME_CHECKED = "QFrame { border: 2px solid #3a8fd1; border-radius: 4px; }"

    def __init__(self, entries, preserve_sv_fn=None, get_checked_fn=None, manual=False,
                 set_mode_fn=None, drop_mode_fn=None, parent=None):
        super().__init__(parent)
        # entries: list of (node, name, qcolor, src, sub_key, ts)
        self._entries = entries
        self._drop_mode_fn = drop_mode_fn or (lambda: False)
        self._set_mode_fn = set_mode_fn or (lambda mode: None)
        self._colors = [e[2] for e in entries]
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
        many = len(entries) > 1
        self._swatch.setToolTip(
            ("Click to change color for all layers of the group" if many else "Click to change color")
            + " — drag a swatch here to apply it"
        )
        self._update_swatch(self.color())
        self._swatch.clicked.connect(self._pick_color)
        # only the "Applied colors" strip can be dropped here: it has its own mode
        self._swatch.color_dropped.connect(
            lambda c: self._apply_new_color(c, add_to_history=False, mode=self._drop_mode_fn())
        )
        layout.addWidget(self._swatch)

        self._name_frame = QtWidgets.QFrame()
        self._name_frame.setStyleSheet(self._FRAME_NORMAL)
        frame_layout = QtWidgets.QHBoxLayout(self._name_frame)
        frame_layout.setContentsMargins(6, 0, 4, 0)
        frame_layout.setSpacing(0)

        names = [e[1] for e in entries]
        if not many:
            label = names[0]
        elif len(names) <= 2:
            label = ", ".join(names)
        else:
            label = f"{names[0]} (+{len(names) - 1} more)"
        name_lbl = QtWidgets.QPushButton(label)
        name_lbl.setFlat(True)
        name_lbl.setStyleSheet("text-align: left; padding: 0; border: none;")
        name_lbl.setCursor(QtCore.Qt.PointingHandCursor)
        if many:
            lines = [f"{e[1]}   {c.name().upper()}" for e, c in zip(entries, self._colors)]
            name_lbl.setToolTip(f"{len(names)} layers in this group:\n" + "\n".join(lines)
                                + "\n\nClick to select them")
        else:
            name_lbl.setToolTip("Click to select this layer in the stack")
        name_lbl.clicked.connect(self._select_layers)
        frame_layout.addWidget(name_lbl, 1)

        if manual:
            link = QtWidgets.QLabel()
            link.setPixmap(_draw_icon("link", "#3a8fd1", 14).pixmap(14, 14))
            link.setToolTip("Grouped manually — use Ungroup to undo")
            frame_layout.addWidget(link)
            frame_layout.addSpacing(4)

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

    def color(self):
        """Representative color of the group (its first member)."""
        return self._colors[0]

    def colors(self):
        return list(self._colors)

    def set_colors_direct(self, colors):
        """Write one color per member as-is (no hue-only transform, no history)."""
        self._colors = list(colors)
        self._update_swatch(self.color())
        for (_node, name, _, src, sub_key, _ts), c in zip(self._entries, self._colors):
            try:
                _apply_color(src, c, sub_key)
            except Exception as e:
                logging.error(f"VG Palette: could not update '{name}': {e}")

    def _apply_new_color(self, new_color, add_to_history=True, _cascade=True, mode=None):
        """*mode* overrides the panel's apply mode (None = use it; False = full color)."""
        if mode is None:
            mode = self._preserve_sv_fn()
        names = []
        for i, (_node, name, _, src, sub_key, _ts) in enumerate(self._entries):
            target = _apply_hue_only(new_color, self._colors[i], mode) if mode else new_color
            try:
                _apply_color(src, target, sub_key)
                self._colors[i] = target
                names.append(name)
            except Exception as e:
                logging.error(f"VG Palette: could not update '{name}': {e}")
        self._update_swatch(self.color())
        if names and add_to_history:
            self.color_applied.emit(self.color(), ", ".join(names))
        if _cascade:
            # pass the raw color so each sibling applies its own hue transform
            for row in self._get_checked_fn():
                if row is not self:
                    row._apply_new_color(new_color, add_to_history=False, _cascade=False, mode=mode)

    def _pick_color(self):
        """
        Open the color picker and apply the color live while it is being adjusted.
        The result is always computed from the colors the layers had when the picker
        opened, so switching the apply mode mid-drag never compounds. OK keeps it
        (and records it in the history), Cancel restores every affected row and the mode.
        """
        rows = [self] + [r for r in self._get_checked_fn() if r is not self]
        saved = [(r, r.colors()) for r in rows]
        initial_mode = self._preserve_sv_fn()

        dlg = _ColorPickerDialog(self.color(), initial_mode, self)
        dlg.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        timer = QtCore.QTimer(dlg)   # throttles writes to Painter while the cursor moves
        timer.setSingleShot(True)
        timer.setInterval(50)

        def apply_live():
            color, mode = dlg.currentColor(), dlg.mode()
            for row, originals in saved:
                try:
                    row.set_colors_direct(
                        [_apply_hue_only(color, o, mode) if mode else color for o in originals]
                    )
                except RuntimeError:  # row was removed meanwhile
                    pass

        def on_accepted():
            timer.stop()
            apply_live()
            self.color_applied.emit(self.color(), ", ".join(e[1] for e in self._entries))

        def on_rejected():
            timer.stop()
            self._set_mode_fn(initial_mode)
            for row, colors in saved:
                try:
                    row.set_colors_direct(colors)
                except RuntimeError:
                    pass

        timer.timeout.connect(apply_live)
        dlg.currentColorChanged.connect(lambda _c: timer.start())
        dlg.modeChanged.connect(self._set_mode_fn)   # the panel's default follows the choice
        dlg.accepted.connect(on_accepted)
        dlg.rejected.connect(on_rejected)
        self._picker = dlg  # keep a reference while the dialog is open
        dlg.open()

    def _select_layers(self):
        """Select the group's layers; members of other texture sets switch the active one first."""
        try:
            ts = self._entries[0][5]
            if textureset.get_active_stack().material().name != ts.name:
                textureset.set_active_stack(ts.get_stack())
            layerstack.set_selected_nodes(
                [e[0] for e in self._entries if e[5].name == ts.name]
            )
        except Exception as e:
            logging.error(f"VG Palette: could not select layers: {e}")


class _WideCombo(QtWidgets.QComboBox):
    """Combo box whose popup list is at least as wide as its longest item."""

    def showPopup(self):
        view = self.view()
        view.setMinimumWidth(max(self.width(), view.sizeHintForColumn(0) + 24))
        super().showPopup()


class PalettePanel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Base Color Manager")
        self.setMinimumWidth(280)

        self._project_was_open = None
        self._picker_mode = _MODE_HUE   # remembered between color picker sessions
        self._connect_events()

        from PySide6.QtCore import QTimer
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(500)
        self._poll_timer.timeout.connect(self._check_project_state)
        self._poll_timer.start()

        root = QtWidgets.QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(8, 8, 8, 8)

        def section(text):
            """Small grey label followed by a separator line."""
            row = QtWidgets.QHBoxLayout()
            lbl = QtWidgets.QLabel(text)
            lbl.setStyleSheet("color: #888; font-size: 11px;")
            line = QtWidgets.QFrame()
            line.setFrameShape(QtWidgets.QFrame.HLine)
            line.setFrameShadow(QtWidgets.QFrame.Sunken)
            row.addWidget(lbl)
            row.addWidget(line, 1)
            root.addLayout(row)

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
        refresh_btn.setToolTip("Rescan the project")
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn)
        root.addLayout(header)

        # ── 1. Snapshots ─────────────────────────────────────────────────────
        section("Snapshots")
        snap_row = QtWidgets.QHBoxLayout()
        snap_row.setSpacing(6)
        self._snap_combo = _WideCombo()
        self._snap_combo.setFixedHeight(32)
        self._snap_combo.setMinimumWidth(40)
        self._snap_combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self._snap_combo.setToolTip(
            "Snapshots of every Base Color in every Texture Set, stored in the project file.\n"
            "'Default' is taken automatically the first time the panel opens on a project."
        )
        snap_row.addWidget(self._snap_combo, 1)
        for kind, variant, tip, slot in (
            ("add", "secondary", "Save as…\nSave the current colors of all Texture Sets as a named snapshot", self._on_snapshot_save),
            ("restore", "accent", "Restore\nRestore the selected snapshot (current state is kept as an auto backup)", self._on_snapshot_restore),
            ("delete", "quiet", "Delete\nDelete the selected snapshot", self._on_snapshot_delete),
        ):
            btn = _spectrum_icon_button(kind, variant, tip)
            btn.clicked.connect(slot)
            snap_row.addWidget(btn)
        root.addLayout(snap_row)

        self._snap_status = QtWidgets.QLabel("")
        self._snap_status.setWordWrap(True)
        self._snap_status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._snap_status)

        # ── 2. Layers: what is listed, how it is grouped, then the list itself ──
        section("Layers")
        self._ignore_hidden_cb = QtWidgets.QCheckBox("Ignore hidden layers")
        self._ignore_hidden_cb.setChecked(True)
        self._ignore_hidden_cb.stateChanged.connect(lambda _: self.refresh())
        root.addWidget(self._ignore_hidden_cb)

        self._merge_cb = QtWidgets.QCheckBox("Group colors")
        self._merge_cb.setChecked(True)
        self._merge_cb.setToolTip(
            "Merge layers with the same or a similar color into one row,\n"
            "across all Texture Sets. Unchecked: one row per layer\n"
            "(manual groups are suspended too)."
        )
        self._sort_cb = QtWidgets.QCheckBox("Sort by hue")
        self._sort_cb.setChecked(True)
        self._sort_cb.setToolTip(
            "Order the rows by hue, then lightness (grays last),\n"
            "so close colors sit next to each other.\n"
            "Unchecked: order of the layers in the project."
        )
        self._sort_cb.stateChanged.connect(lambda _: self._group_timer.start())
        group_opts = QtWidgets.QHBoxLayout()
        group_opts.addWidget(self._merge_cb)
        group_opts.addWidget(self._sort_cb)
        group_opts.addStretch()
        root.addLayout(group_opts)

        sim_row = QtWidgets.QHBoxLayout()
        sim_lbl = QtWidgets.QLabel("Similarity")
        sim_lbl.setFixedWidth(64)
        self._similarity_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self._similarity_slider.setRange(0, 30)
        self._similarity_slider.setValue(30)   # start grouped as much as possible; lower it for more colors
        self._similarity_slider.setToolTip(
            "0: only identical colors are grouped.\n"
            "Higher: colors closer than this perceptual distance (ΔE) are grouped too."
        )
        self._similarity_val = QtWidgets.QLabel(f"ΔE {self._similarity_slider.value()}")
        self._similarity_val.setFixedWidth(52)
        self._similarity_val.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        sim_row.addWidget(sim_lbl)
        sim_row.addWidget(self._similarity_slider, 1)
        sim_row.addWidget(self._similarity_val)
        root.addLayout(sim_row)

        self._group_timer = QtCore.QTimer(self)
        self._group_timer.setSingleShot(True)
        self._group_timer.setInterval(200)
        self._group_timer.timeout.connect(self.refresh)
        self._similarity_slider.valueChanged.connect(
            lambda v: self._similarity_val.setText(f"ΔE {v}" if v else "Identical")
        )
        self._similarity_slider.valueChanged.connect(lambda _: self._group_timer.start())

        def _on_group_toggled(state):
            self._similarity_slider.setEnabled(bool(state))
            self._group_timer.start()
        self._merge_cb.stateChanged.connect(_on_group_toggled)

        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._scroll.setMinimumHeight(140)

        self._container = QtWidgets.QWidget()
        self._rows_layout = QtWidgets.QVBoxLayout(self._container)
        self._rows_layout.setSpacing(4)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.addStretch()
        self._scroll.setWidget(self._container)
        root.addWidget(self._scroll, 1)

        # Acts on the checked rows, so it sits right under the list.
        self._forced = []  # list of sets of entry keys the user grouped by hand
        force_row = QtWidgets.QHBoxLayout()
        force_row.setSpacing(6)
        group_btn = _spectrum_button(
            "Group selected", "secondary",
            "Merge the checked rows into one group, whatever their colors.\n"
            "Kept until the panel is closed.")
        group_btn.clicked.connect(self._group_checked)
        ungroup_btn = _spectrum_button(
            "Ungroup", "quiet",
            "Undo the manual grouping of the checked rows.\n"
            "Automatic grouping (Similarity) is not affected.")
        ungroup_btn.clicked.connect(self._ungroup_checked)
        force_row.addWidget(group_btn, 1)
        force_row.addWidget(ungroup_btn, 1)
        root.addLayout(force_row)

        # ── 3. Applied colors: dropping or clicking one applies hue + saturation ──
        swatch_header = QtWidgets.QHBoxLayout()
        swatch_lbl = QtWidgets.QLabel("Applied colors")
        swatch_lbl.setStyleSheet("color: #888; font-size: 11px;")
        swatch_line = QtWidgets.QFrame()
        swatch_line.setFrameShape(QtWidgets.QFrame.HLine)
        swatch_line.setFrameShadow(QtWidgets.QFrame.Sunken)
        swatch_header.addWidget(swatch_lbl)
        swatch_header.addWidget(swatch_line, 1)
        clear_btn = _spectrum_button("Clear", "quiet", "Clear color history")
        clear_btn.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        clear_btn.clicked.connect(self._clear_swatches)
        swatch_header.addWidget(clear_btn)
        root.addLayout(swatch_header)

        swatch_scroll = QtWidgets.QScrollArea()
        swatch_scroll.setWidgetResizable(True)
        swatch_scroll.setMaximumHeight(90)
        swatch_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        swatch_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        swatch_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        self._swatch_container = QtWidgets.QWidget()
        self._swatch_layout = _FlowLayout(self._swatch_container, spacing=4)
        self._swatch_container.setLayout(self._swatch_layout)
        swatch_scroll.setWidget(self._swatch_container)
        root.addWidget(swatch_scroll)

        # ── 4. Relative adjustment of the checked rows ───────────────────────
        section("Adjust (relative)")
        self._offset_baseline = None   # list of (row, original colors) while sliders are away from 0
        self._offset_timer = QtCore.QTimer(self)
        self._offset_timer.setSingleShot(True)
        self._offset_timer.setInterval(80)
        self._offset_timer.timeout.connect(self._apply_offset)

        self._sat_slider, self._sat_val = self._make_offset_slider(
            root, "Saturation", "Shift saturation of the checked rows (all rows if none checked),\n"
            "relative to their current value.")
        self._light_slider, self._light_val = self._make_offset_slider(
            root, "Lightness", "Shift lightness of the checked rows (all rows if none checked),\n"
            "relative to their current value.")

        self._scope_lbl = QtWidgets.QLabel("")
        self._scope_lbl.setWordWrap(True)
        self._scope_lbl.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._scope_lbl)

        adjust_btns = QtWidgets.QHBoxLayout()
        adjust_btns.setSpacing(6)
        self._compare_btn = _spectrum_button(
            "Compare", "secondary",
            "Hold to see the colors as they were before this adjustment")
        self._compare_btn.setEnabled(False)
        self._compare_btn.pressed.connect(self._compare_show_original)
        self._compare_btn.released.connect(self._compare_show_adjusted)
        reset_btn = _spectrum_button(
            "Reset", "quiet", "Put the colors back as they were before this adjustment")
        reset_btn.clicked.connect(self._reset_offset)
        commit_btn = _spectrum_button(
            "Apply", "accent", "Keep the adjusted colors and reset the sliders to 0")
        commit_btn.clicked.connect(self._commit_offset)
        for b in (self._compare_btn, reset_btn, commit_btn):
            adjust_btns.addWidget(b, 1)
        root.addLayout(adjust_btns)

        self.refresh()

    def _blend_mode(self):
        """
        Mode used for color picks: False (full color), 'hue' (keep S+V) or 'hue_sat'
        (keep V only). Chosen in the color picker, which hands it back via _set_blend_mode.
        """
        return self._picker_mode

    # ── Relative adjustment ──────────────────────────────────────────────────

    def _make_offset_slider(self, root, label, tooltip):
        row = QtWidgets.QHBoxLayout()
        lbl = QtWidgets.QLabel(label)
        lbl.setFixedWidth(64)
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(-100, 100)
        slider.setValue(0)
        slider.setToolTip(tooltip)
        val = QtWidgets.QLabel("0%")
        val.setFixedWidth(38)
        val.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        slider.valueChanged.connect(lambda v: val.setText(f"{v:+d}%" if v else "0%"))
        slider.valueChanged.connect(lambda _: self._offset_timer.start())
        row.addWidget(lbl)
        row.addWidget(slider, 1)
        row.addWidget(val)
        root.addLayout(row)
        return slider, val

    def _all_rows(self):
        rows = []
        for i in range(self._rows_layout.count() - 1):
            item = self._rows_layout.itemAt(i)
            w = item.widget() if item else None
            if w is not None and hasattr(w, "set_colors_direct"):
                rows.append(w)
        return rows

    def _offset_targets(self):
        """Checked rows, or every row when none is checked."""
        return self._get_checked_rows() or self._all_rows()

    def _update_scope_label(self):
        checked = len(self._get_checked_rows())
        total = len(self._all_rows())
        if checked:
            self._scope_lbl.setText(f"Affects {checked} checked row{'s' if checked != 1 else ''}")
        else:
            self._scope_lbl.setText(f"Affects all {total} rows (check rows to restrict)")

    def _on_selection_changed(self, _state=None):
        """Keep an adjustment in progress in sync with the checked rows."""
        self._update_scope_label()
        if self._offset_baseline is None:
            return
        old = {id(r): (r, b) for r, b in self._offset_baseline}
        new_baseline = []
        for row in self._offset_targets():
            new_baseline.append(old.pop(id(row), None) or (row, row.colors()))
        for row, bases in old.values():  # rows no longer targeted go back to their original colors
            try:
                row.set_colors_direct(bases)
            except RuntimeError:
                pass
        self._offset_baseline = new_baseline
        self._compare_btn.setEnabled(bool(new_baseline))
        self._apply_offset()

    def _apply_offset(self):
        if not project.is_open():
            return
        if self._offset_baseline is None:
            targets = self._offset_targets()
            self._offset_baseline = [(r, r.colors()) for r in targets]
            self._compare_btn.setEnabled(bool(self._offset_baseline))
        d_sat = self._sat_slider.value() / 100.0
        d_light = self._light_slider.value() / 100.0
        for row, bases in self._offset_baseline:
            try:
                # each member is offset from its own color, so group differences are kept
                row.set_colors_direct([_offset_color(b, d_sat, d_light) for b in bases])
            except RuntimeError:  # row was deleted by a refresh
                pass

    def _compare_show_original(self):
        self._offset_timer.stop()
        for row, bases in self._offset_baseline or []:
            try:
                row.set_colors_direct(bases)
            except RuntimeError:
                pass

    def _compare_show_adjusted(self):
        if self._offset_baseline is not None:
            self._apply_offset()

    def _zero_sliders(self):
        self._compare_btn.setEnabled(False)
        for s in (self._sat_slider, self._light_slider):
            s.blockSignals(True)
            s.setValue(0)
            s.blockSignals(False)
        self._sat_val.setText("0%")
        self._light_val.setText("0%")

    def _reset_offset(self):
        self._offset_timer.stop()
        if self._offset_baseline:
            for row, bases in self._offset_baseline:
                try:
                    row.set_colors_direct(bases)
                except RuntimeError:
                    pass
        self._offset_baseline = None
        self._zero_sliders()

    def _commit_offset(self):
        self._offset_timer.stop()
        if self._offset_baseline is not None or self._sat_slider.value() or self._light_slider.value():
            self._apply_offset()
        self._offset_baseline = None
        self._zero_sliders()

    # ── Snapshots ────────────────────────────────────────────────────────────

    def _refresh_snapshots(self, select=None):
        names = list((load_snapshots() or {}).keys()) if project.is_open() else []
        current = select or self._snap_combo.currentText()
        self._snap_combo.blockSignals(True)
        self._snap_combo.clear()
        self._snap_combo.addItems(names)
        if current in names:
            self._snap_combo.setCurrentText(current)
        self._snap_combo.blockSignals(False)
        self._snap_combo.setEnabled(bool(names))

    def _on_snapshot_save(self):
        if not project.is_open():
            return
        name, ok = QtWidgets.QInputDialog.getText(self, "Save Snapshot", "Snapshot name:")
        name = name.strip()
        if not ok or not name:
            return
        if name in (load_snapshots() or {}):
            answer = QtWidgets.QMessageBox.question(
                self, "Save Snapshot", f"'{name}' already exists. Overwrite it?"
            )
            if answer != QtWidgets.QMessageBox.Yes:
                return
        try:
            count = save_snapshot(name)
            self._snap_status.setText(f"Saved '{name}' ({count} colors). Save the project to keep it.")
        except Exception as e:
            logging.error(f"VG Palette: could not save snapshot: {e}")
            return
        self._refresh_snapshots(select=name)

    def _on_snapshot_restore(self):
        name = self._snap_combo.currentText()
        if not name or not project.is_open():
            return
        answer = QtWidgets.QMessageBox.question(
            self, "Restore Snapshot",
            f"Restore '{name}'?\nCurrent colors are kept in '{BACKUP_SNAPSHOT}'."
        )
        if answer != QtWidgets.QMessageBox.Yes:
            return
        try:
            if name != BACKUP_SNAPSHOT:
                save_snapshot(BACKUP_SNAPSHOT)
            restored, missing = restore_snapshot(name)
        except Exception as e:
            logging.error(f"VG Palette: could not restore snapshot: {e}")
            return
        msg = f"Restored '{name}': {restored} colors"
        if missing:
            msg += f", {missing} layers not found"
        self._snap_status.setText(msg + ".")
        self._refresh_snapshots(select=name)
        self.refresh()

    def _on_snapshot_delete(self):
        name = self._snap_combo.currentText()
        if not name or not project.is_open():
            return
        answer = QtWidgets.QMessageBox.question(self, "Delete Snapshot", f"Delete '{name}'?")
        if answer != QtWidgets.QMessageBox.Yes:
            return
        delete_snapshot(name)
        self._snap_status.setText(f"Deleted '{name}'.")
        self._refresh_snapshots()

    def _connect_events(self):
        event.DISPATCHER.connect_strong(event.ProjectOpened, self._on_project_event)
        event.DISPATCHER.connect_strong(event.ProjectClosed, self._on_project_event)

    def _disconnect_events(self):
        try:
            event.DISPATCHER.disconnect(event.ProjectOpened, self._on_project_event)
            event.DISPATCHER.disconnect(event.ProjectClosed, self._on_project_event)
        except Exception:
            pass

    def cleanup(self):
        """Stop the poll timer and disconnect Painter events. Safe to call multiple times."""
        self._poll_timer.stop()
        self._disconnect_events()

    def closeEvent(self, e):
        self.cleanup()
        super().closeEvent(e)

    def _on_project_event(self, e):
        self.refresh()

    def _check_project_state(self):
        """Timer fallback: the list covers every texture set, so only a project open/close needs a rescan."""
        if project.is_open() != self._project_was_open:
            self.refresh()

    def _clear_rows(self):
        while self._rows_layout.count() > 1:
            item = self._rows_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def refresh(self):
        self._offset_timer.stop()
        self._offset_baseline = None
        self._zero_sliders()
        self._clear_rows()

        if ensure_default_snapshot():
            self._snap_status.setText(f"'{DEFAULT_SNAPSHOT}' snapshot created from current colors.")
        self._refresh_snapshots()

        self._project_was_open = project.is_open()
        self._update_scope_label()
        if not self._project_was_open:
            self._add_info("No project open.")
            return

        entries = collect_all(ignore_hidden=self._ignore_hidden_cb.isChecked())

        if not entries:
            self._add_info("No fill layers with Base Color found.")
            return

        rows = self._build_rows(entries)
        for i, row in enumerate(rows):
            row.removed.connect(self._remove_row)
            row.color_applied.connect(self._add_to_swatches)
            row._checkbox.stateChanged.connect(self._on_selection_changed)
            self._rows_layout.insertWidget(i, row)
        self._update_scope_label()

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
        preserve_sv = self._blend_mode
        get_checked = self._get_checked_rows
        if not self._merge_cb.isChecked():
            groups = [[e] for e in entries]
        else:
            groups = group_entries(entries, self._similarity_slider.value())
        manual = []
        if self._merge_cb.isChecked():
            groups, manual = self._apply_forced_groups(groups)
        if self._sort_cb.isChecked():
            groups.sort(key=lambda g: _hue_sort_key(g[0][2]))
        return [_ColorRow(group, preserve_sv, get_checked,
                          manual=any(group is m for m in manual),
                          set_mode_fn=self._set_blend_mode,
                          drop_mode_fn=self._drop_mode)
                for group in groups]

    @staticmethod
    def _drop_mode():
        """A color from the Applied colors strip is always applied as hue + saturation."""
        return _MODE_HUE_SAT

    def _set_blend_mode(self, mode):
        self._picker_mode = mode

    @staticmethod
    def _entry_key(entry):
        node, name, _, _, sub_key, ts = entry
        uid = _node_uid(node)
        return (ts.name, uid if uid is not None else name, sub_key or "")

    def _apply_forced_groups(self, groups):
        """
        Merge every automatic group that contains a member of a hand-made group.
        Returns (groups, manual_groups) where manual_groups are the merged ones.
        """
        manual = []
        for forced in self._forced:
            hit = [g for g in groups if any(self._entry_key(e) in forced for e in g)]
            if len(hit) < 2:
                # a single group already holds the whole selection: still a manual group
                if (hit and not any(hit[0] is m for m in manual)
                        and sum(self._entry_key(e) in forced for e in hit[0]) >= 2):
                    manual.append(hit[0])
                continue
            merged = [e for g in hit for e in g]
            first = next(i for i, g in enumerate(groups) if g is hit[0])
            groups = [g for g in groups if not any(g is h for h in hit)]
            groups.insert(first, merged)
            manual = [m for m in manual if not any(m is h for h in hit)]
            manual.append(merged)
        return groups, manual

    def _checked_keys(self):
        return {self._entry_key(e) for row in self._get_checked_rows() for e in row._entries}

    def _group_checked(self):
        rows = self._get_checked_rows()
        if len(rows) < 2:
            self._snap_status.setText("Check at least two rows to group them.")
            return
        keys = self._checked_keys()
        # fold any existing hand-made group touched by the selection into the new one
        for old in [f for f in self._forced if f & keys]:
            keys |= old
            self._forced.remove(old)
        self._forced.append(keys)
        self.refresh()

    def _ungroup_checked(self):
        keys = self._checked_keys()
        before = len(self._forced)
        self._forced = [f for f in self._forced if not f & keys]
        if len(self._forced) != before:
            self.refresh()
        else:
            self._snap_status.setText("The checked rows have no manual grouping to undo.")

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
        hue_only = self._drop_mode()
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
                    color_to_apply = _apply_hue_only(qcolor, current_color, hue_only)
                _apply_color(src, color_to_apply, sub_key)
            except Exception as e:
                logging.warning(f"VG Palette: could not apply swatch: {e}")

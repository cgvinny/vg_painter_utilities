##########################################################################
#
# Copyright 2024 Vincent GAULT - Adobe
# All Rights Reserved.
#
##########################################################################

"""
PySide6 panel for the Collection system.

Classes
-------
CollectionSlotWidget      — one editable row (color swatch + name + delete)
CollectionEditorDialog    — modal dialog to create a new Collection
CollectionManageDialog    — modal dialog to edit an existing Collection + Painter actions
CollectionRowWidget       — one row in the flat collections list
CollectionPanel           — dockable panel: flat list of rows + New Collection button
"""

__author__ = "Vincent GAULT - Adobe"

from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt

from substance_painter import ui, project, resource, layerstack, textureset, logging
from vg_pt_utils import vg_collection
from vg_pt_utils.vg_collection import (
    Collection, CollectionSlot, CollectionLayerBuilder,
    get_collection_folder, find_spsm, find_collection_group, save_as_smart_material,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _color_to_qcolor(color: list) -> QtGui.QColor:
    r, g, b = color
    return QtGui.QColor.fromRgbF(r, g, b)


def _qcolor_to_color(qc: QtGui.QColor) -> list:
    return [qc.redF(), qc.greenF(), qc.blueF()]


def _swatch_pixmap(color: list, size: int = 18) -> QtGui.QPixmap:
    pix = QtGui.QPixmap(size, size)
    pix.fill(_color_to_qcolor(color))
    return pix


# ---------------------------------------------------------------------------
# CollectionSlotWidget — one row in the slot editor
# ---------------------------------------------------------------------------

class CollectionSlotWidget(QtWidgets.QWidget):
    """
    A single row in the slot editor:
      [color swatch button]  [material name field]  [delete button]
    """
    deleted = QtCore.Signal(object)  # emits self

    def __init__(self, slot: CollectionSlot, parent=None):
        super().__init__(parent)
        self._slot = CollectionSlot(slot.material_name, list(slot.color))

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)

        self._color_btn = QtWidgets.QPushButton()
        self._color_btn.setFixedSize(28, 22)
        self._color_btn.setFlat(True)
        self._color_btn.setCursor(Qt.PointingHandCursor)
        self._color_btn.clicked.connect(self._pick_color)
        self._refresh_swatch()
        layout.addWidget(self._color_btn)

        self._name_edit = QtWidgets.QLineEdit(slot.material_name)
        self._name_edit.setPlaceholderText("Material name…")
        self._name_edit.textChanged.connect(lambda t: setattr(self._slot, "material_name", t))
        layout.addWidget(self._name_edit, 1)

        del_btn = QtWidgets.QPushButton("✕")
        del_btn.setFixedSize(24, 22)
        del_btn.setFlat(True)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setToolTip("Remove slot")
        del_btn.clicked.connect(lambda: self.deleted.emit(self))
        layout.addWidget(del_btn)

    def _pick_color(self):
        qc = QtWidgets.QColorDialog.getColor(
            _color_to_qcolor(self._slot.color),
            self,
            "Choose ID Map Color",
        )
        if qc.isValid():
            self._slot.color = _qcolor_to_color(qc)
            self._refresh_swatch()

    def _refresh_swatch(self):
        self._color_btn.setIcon(QtGui.QIcon(_swatch_pixmap(self._slot.color, 18)))
        self._color_btn.setIconSize(QtCore.QSize(18, 18))

    def get_slot(self) -> CollectionSlot:
        self._slot.material_name = self._name_edit.text().strip()
        return CollectionSlot(self._slot.material_name, list(self._slot.color))


# ---------------------------------------------------------------------------
# CollectionEditorDialog — modal dialog to create a NEW collection
# ---------------------------------------------------------------------------

class CollectionEditorDialog(QtWidgets.QDialog):
    """
    Modal dialog to create a new Collection.

    On accept(), retrieve the result with .result_collection().
    """

    _DEFAULT_COLORS = [
        ([1.0, 0.0, 0.0], "Material 1"),
        ([0.0, 1.0, 0.0], "Material 2"),
        ([0.0, 0.0, 1.0], "Material 3"),
        ([0.0, 1.0, 1.0], "Material 4"),
        ([1.0, 0.0, 1.0], "Material 5"),
        ([1.0, 1.0, 0.0], "Material 6"),
        ([1.0, 0.5, 0.0], "Material 7"),
        ([0.5, 1.0, 0.0], "Material 8"),
        ([0.0, 0.5, 1.0], "Material 9"),
        ([1.0, 0.0, 0.5], "Material 10"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent or ui.get_main_window())
        self._slot_widgets: list[CollectionSlotWidget] = []
        self._result: Collection = None

        self.setWindowTitle("New Collection")
        self.setMinimumSize(460, 500)
        self._build_ui()
        self._ask_slot_count()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setSpacing(10)

        form = QtWidgets.QFormLayout()
        form.setRowWrapPolicy(QtWidgets.QFormLayout.DontWrapRows)

        self._name_edit = QtWidgets.QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Organic Character")
        form.addRow("Name *", self._name_edit)

        self._author_edit = QtWidgets.QLineEdit()
        self._author_edit.setPlaceholderText("e.g. Studio Name")
        form.addRow("Author", self._author_edit)

        self._desc_edit = QtWidgets.QLineEdit()
        self._desc_edit.setPlaceholderText("Short description…")
        form.addRow("Description", self._desc_edit)

        root.addLayout(form)

        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        sep.setFrameShadow(QtWidgets.QFrame.Sunken)
        root.addWidget(sep)

        slots_header = QtWidgets.QHBoxLayout()
        slots_header.addWidget(QtWidgets.QLabel("<b>Material Slots</b>"))
        slots_header.addStretch()
        add_btn = QtWidgets.QPushButton("+ Add Slot")
        add_btn.setFixedWidth(90)
        add_btn.clicked.connect(self._add_slot)
        slots_header.addWidget(add_btn)
        root.addLayout(slots_header)

        self._slots_area = QtWidgets.QScrollArea()
        self._slots_area.setWidgetResizable(True)
        self._slots_area.setFrameShape(QtWidgets.QFrame.NoFrame)

        self._slots_container = QtWidgets.QWidget()
        self._slots_layout = QtWidgets.QVBoxLayout(self._slots_container)
        self._slots_layout.setContentsMargins(0, 0, 0, 0)
        self._slots_layout.setSpacing(0)
        self._slots_layout.addStretch()

        self._slots_area.setWidget(self._slots_container)
        root.addWidget(self._slots_area, 1)

        btn_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Cancel)
        setup_btn = btn_box.addButton(
            "Setup Collection Content", QtWidgets.QDialogButtonBox.AcceptRole
        )
        setup_btn.setDefault(True)
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        root.addWidget(btn_box)

    def _ask_slot_count(self):
        count, ok = QtWidgets.QInputDialog.getInt(
            self,
            "Number of Materials",
            "How many material slots? (1 – 10)",
            4, 1, 10, 1,
        )
        if ok:
            for i in range(count):
                color, name = (
                    self._DEFAULT_COLORS[i]
                    if i < len(self._DEFAULT_COLORS)
                    else ([0.5, 0.5, 0.5], f"Material {i + 1}")
                )
                self._add_slot(CollectionSlot(name, list(color)))

    def _add_slot(self, slot=None):
        if not isinstance(slot, CollectionSlot):
            idx = len(self._slot_widgets)
            color, name = (
                self._DEFAULT_COLORS[idx]
                if idx < len(self._DEFAULT_COLORS)
                else ([0.5, 0.5, 0.5], f"Material {idx + 1}")
            )
            slot = CollectionSlot(name, list(color))
        widget = CollectionSlotWidget(slot, self._slots_container)
        widget.deleted.connect(self._remove_slot)
        self._slots_layout.insertWidget(self._slots_layout.count() - 1, widget)
        self._slot_widgets.append(widget)

    def _remove_slot(self, widget: CollectionSlotWidget):
        self._slots_layout.removeWidget(widget)
        widget.deleteLater()
        self._slot_widgets.remove(widget)

    def _on_accept(self):
        name = self._name_edit.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Validation", "Collection name is required.")
            return
        slots = [w.get_slot() for w in self._slot_widgets if w.get_slot().material_name]
        if not slots:
            QtWidgets.QMessageBox.warning(self, "Validation", "Add at least one slot.")
            return
        self._result = Collection(
            name=name,
            author=self._author_edit.text().strip(),
            description=self._desc_edit.text().strip(),
            slots=slots,
        )
        self.accept()

    def result_collection(self) -> Collection:
        return self._result


# ---------------------------------------------------------------------------
# CollectionManageDialog — edit an existing collection + Painter actions
# ---------------------------------------------------------------------------

class CollectionManageDialog(QtWidgets.QDialog):
    """
    Modal dialog to edit an existing Collection and run Painter operations on it.

    Sections:
      - Collection Settings: name, author, description, slots
      - Painter Actions: Generate in Stack, Save as Smart Material

    On accept(), retrieve the updated collection with .result_collection().
    The original name (before any edits) is available via .old_name.
    """

    def __init__(self, collection: Collection, parent=None):
        super().__init__(parent or ui.get_main_window())
        self._old_name = collection.name
        self._collection = collection.copy()
        self._slot_widgets: list[CollectionSlotWidget] = []
        self._result: Collection = None

        self.setWindowTitle(f"Manage — {collection.name}")
        self.setMinimumSize(520, 580)
        self._build_ui()
        self._populate()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setSpacing(10)

        # ---- Collection Settings group ----
        settings_group = QtWidgets.QGroupBox("Collection Settings")
        sg_layout = QtWidgets.QVBoxLayout(settings_group)
        sg_layout.setSpacing(8)

        form = QtWidgets.QFormLayout()
        form.setRowWrapPolicy(QtWidgets.QFormLayout.DontWrapRows)

        self._name_edit = QtWidgets.QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Organic Character")
        form.addRow("Name *", self._name_edit)

        self._author_edit = QtWidgets.QLineEdit()
        self._author_edit.setPlaceholderText("e.g. Studio Name")
        form.addRow("Author", self._author_edit)

        self._desc_edit = QtWidgets.QLineEdit()
        self._desc_edit.setPlaceholderText("Short description…")
        form.addRow("Description", self._desc_edit)

        sg_layout.addLayout(form)

        slots_header = QtWidgets.QHBoxLayout()
        slots_header.addWidget(QtWidgets.QLabel("<b>Material Slots</b>"))
        slots_header.addStretch()
        add_slot_btn = QtWidgets.QPushButton("+ Add Slot")
        add_slot_btn.setFixedWidth(90)
        add_slot_btn.clicked.connect(self._add_slot)
        slots_header.addWidget(add_slot_btn)
        sg_layout.addLayout(slots_header)

        self._slots_area = QtWidgets.QScrollArea()
        self._slots_area.setWidgetResizable(True)
        self._slots_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._slots_area.setMinimumHeight(100)
        self._slots_area.setMaximumHeight(200)

        self._slots_container = QtWidgets.QWidget()
        self._slots_layout = QtWidgets.QVBoxLayout(self._slots_container)
        self._slots_layout.setContentsMargins(0, 0, 0, 0)
        self._slots_layout.setSpacing(0)
        self._slots_layout.addStretch()

        self._slots_area.setWidget(self._slots_container)
        sg_layout.addWidget(self._slots_area)

        root.addWidget(settings_group, 1)

        # ---- Painter Actions group ----
        actions_group = QtWidgets.QGroupBox("Painter Actions")
        actions_layout = QtWidgets.QVBoxLayout(actions_group)
        actions_layout.setSpacing(8)

        # Generate in Stack row
        gen_row = QtWidgets.QHBoxLayout()
        gen_btn = QtWidgets.QPushButton("Generate in Stack")
        gen_btn.setFixedWidth(160)
        gen_btn.setToolTip(
            "Create the layer group structure in the active texture set.\n"
            "Color Selection effects are linked to the baked ID map if one exists."
        )
        gen_btn.clicked.connect(self._on_generate)
        gen_row.addWidget(gen_btn)
        self._gen_status = QtWidgets.QLabel()
        self._gen_status.setTextFormat(Qt.RichText)
        self._gen_status.setWordWrap(True)
        gen_row.addWidget(self._gen_status, 1)
        actions_layout.addLayout(gen_row)

        # Save / Update Smart Material row
        sm_row = QtWidgets.QHBoxLayout()
        self._sm_btn = QtWidgets.QPushButton()   # text set in _populate()
        self._sm_btn.setFixedWidth(200)
        self._sm_btn.setToolTip(
            "Find the collection group in the active layer stack and save it as a .spsm file.\n"
            "Prerequisite: generate the collection structure first, fill in your layers, then save."
        )
        self._sm_btn.clicked.connect(self._on_save_sm)
        sm_row.addWidget(self._sm_btn)
        self._sm_status = QtWidgets.QLabel()
        self._sm_status.setTextFormat(Qt.RichText)
        self._sm_status.setWordWrap(True)
        sm_row.addWidget(self._sm_status, 1)
        actions_layout.addLayout(sm_row)

        root.addWidget(actions_group)

        # ---- Dialog buttons ----
        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        root.addWidget(btn_box)

    def _populate(self):
        self._name_edit.setText(self._collection.name)
        self._author_edit.setText(self._collection.author)
        self._desc_edit.setText(self._collection.description)
        for slot in self._collection.slots:
            self._add_slot(slot)
        self._refresh_sm_button()

    # ------------------------------------------------------------------
    # Slot management
    # ------------------------------------------------------------------

    def _add_slot(self, slot=None):
        if not isinstance(slot, CollectionSlot):
            slot = CollectionSlot(f"Material {len(self._slot_widgets) + 1}", [0.5, 0.5, 0.5])
        widget = CollectionSlotWidget(slot, self._slots_container)
        widget.deleted.connect(self._remove_slot)
        self._slots_layout.insertWidget(self._slots_layout.count() - 1, widget)
        self._slot_widgets.append(widget)

    def _remove_slot(self, widget: CollectionSlotWidget):
        self._slots_layout.removeWidget(widget)
        widget.deleteLater()
        self._slot_widgets.remove(widget)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _current_collection(self) -> Collection:
        """Build a Collection from the current dialog field values."""
        return Collection(
            name=self._name_edit.text().strip(),
            author=self._author_edit.text().strip(),
            description=self._desc_edit.text().strip(),
            slots=[w.get_slot() for w in self._slot_widgets if w.get_slot().material_name],
        )

    # ------------------------------------------------------------------
    # Painter Actions
    # ------------------------------------------------------------------

    def _on_generate(self):
        if not project.is_open():
            self._gen_status.setText('<font color="#cc4444">No project open.</font>')
            return
        col = self._current_collection()
        if not col.slots:
            self._gen_status.setText('<font color="#cc4444">No slots defined.</font>')
            return
        try:
            builder = CollectionLayerBuilder()
            _, id_map_found = builder.build(col)
        except Exception as e:
            self._gen_status.setText(f'<font color="#cc4444">Error: {e}</font>')
            logging.error(f"VG Collections: generate failed: {e}")
            return

        n = len(col.slots)
        if id_map_found:
            self._gen_status.setText(
                f'<font color="#55aa55">&#10003; {n} group{"s" if n != 1 else ""} created.'
                f' ID map linked.</font>'
            )
        else:
            self._gen_status.setText(
                f'<font color="#55aa55">&#10003; {n} group{"s" if n != 1 else ""} created.</font> '
                f'<font color="gray"><i>No ID map — bake first.</i></font>'
            )

    def _refresh_sm_button(self):
        """Update the SM button label based on whether a .spsm already exists."""
        has_spsm = find_spsm(self._old_name) is not None
        self._sm_btn.setText(
            "Update Smart Material" if has_spsm else "Save as Smart Material"
        )

    def _on_save_sm(self):
        if not project.is_open():
            self._sm_status.setText('<font color="#cc4444">No project open.</font>')
            return
        col = self._current_collection()
        group = find_collection_group(col.name)
        if group is None:
            self._sm_status.setText(
                f'<font color="#cc4444">No group "{col.name}" found in stack.'
                f' Generate first.</font>'
            )
            return

        # If a .spsm already exists, ask before overwriting
        if find_spsm(col.name) is not None:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Overwrite Smart Material?",
                f"A Smart Material is already associated with \"{col.name}\".\n\n"
                "Do you want to overwrite it with the current version "
                "from the layer stack?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return
            # Remove existing .spsm files to avoid accumulation
            dest_folder = get_collection_folder(col.name)
            for old_file in dest_folder.glob("*.spsm"):
                try:
                    old_file.unlink()
                except OSError:
                    pass

        self._sm_btn.setEnabled(False)
        self._sm_status.setText('<font color="gray"><i>Saving…</i></font>')
        QtWidgets.QApplication.processEvents()

        try:
            dest = save_as_smart_material(col.name, group)
        except Exception as e:
            self._sm_status.setText(f'<font color="#cc4444">&#10006; {e}</font>')
            logging.error(f"VG Collections: save_as_smart_material failed: {e}")
            self._sm_btn.setEnabled(True)
            return

        self._sm_status.setText(
            f'<font color="#55aa55">&#10003; Saved.</font> '
            f'<font color="gray">{dest.name}</font>'
        )
        self._sm_btn.setEnabled(True)
        self._refresh_sm_button()   # switch label to "Update Smart Material"

    # ------------------------------------------------------------------
    # Accept
    # ------------------------------------------------------------------

    def _on_accept(self):
        name = self._name_edit.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Validation", "Collection name is required.")
            return
        slots = [w.get_slot() for w in self._slot_widgets if w.get_slot().material_name]
        if not slots:
            QtWidgets.QMessageBox.warning(self, "Validation", "Add at least one slot.")
            return
        self._result = Collection(
            name=name,
            author=self._author_edit.text().strip(),
            description=self._desc_edit.text().strip(),
            slots=slots,
        )
        self.accept()

    @property
    def old_name(self) -> str:
        """The collection name as it was before any edits in this dialog."""
        return self._old_name

    def result_collection(self) -> Collection:
        return self._result


# ---------------------------------------------------------------------------
# CollectionSetupFloater — floating widget shown after collection creation
# ---------------------------------------------------------------------------

class CollectionSetupFloater(QtWidgets.QWidget):
    """
    Frameless toast-style overlay shown after a new collection's layer
    structure has been generated.  The user fills in the layers in Painter,
    then clicks "Save as Smart Material".

    Closing without saving triggers a Save / Discard / Cancel prompt.
    Drag the card to reposition it.
    """

    collection_saved = QtCore.Signal()

    _CARD_BG      = "rgba(32, 32, 35, 235)"
    _CARD_BORDER  = "rgba(255, 255, 255, 22)"
    _BTN_IDLE     = "#2d6a9f"
    _BTN_HOVER    = "#3a7fc0"
    _BTN_PRESSED  = "#1f5080"
    _BTN_DISABLED = "#3a3a3d"

    def __init__(self, collection: Collection, parent=None):
        super().__init__(parent or ui.get_main_window())
        self._collection = collection
        self._saved = False
        self._drag_pos = None

        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setFixedWidth(280)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 8)   # bottom shadow illusion

        card = QtWidgets.QFrame()
        card.setObjectName("floater_card")
        card.setStyleSheet(f"""
            QFrame#floater_card {{
                background-color: {self._CARD_BG};
                border: 1px solid {self._CARD_BORDER};
                border-radius: 8px;
            }}
        """)
        outer.addWidget(card)

        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 10, 12)
        layout.setSpacing(6)

        # ---- Header row ----
        header = QtWidgets.QHBoxLayout()
        header.setSpacing(6)

        indicator = QtWidgets.QLabel("●")
        indicator.setStyleSheet("color: #f0a030; font-size: 7px; padding-top: 1px;")
        header.addWidget(indicator)

        name_lbl = QtWidgets.QLabel(self._collection.name)
        name_lbl.setStyleSheet("color: #d8d8d8; font-size: 11px; font-weight: bold;")
        header.addWidget(name_lbl, 1)

        close_btn = QtWidgets.QToolButton()
        close_btn.setText("×")
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(
            "QToolButton { color: #888; font-size: 16px; border: none; background: transparent; }"
            "QToolButton:hover { color: #ccc; }"
        )
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)

        layout.addLayout(header)

        # ---- Subtitle ----
        sub = QtWidgets.QLabel("Fill in your layers, then save as Smart Material.")
        sub.setStyleSheet("color: #777; font-size: 10px;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        # ---- Status ----
        self._status_lbl = QtWidgets.QLabel()
        self._status_lbl.setTextFormat(Qt.RichText)
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setStyleSheet("font-size: 10px;")
        self._status_lbl.hide()
        layout.addWidget(self._status_lbl)

        # ---- Action button ----
        self._gen_btn = QtWidgets.QPushButton("Save as Smart Material")
        self._gen_btn.setFixedHeight(30)
        self._gen_btn.setCursor(Qt.PointingHandCursor)
        self._gen_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._BTN_IDLE};
                color: #ffffff;
                border: none;
                border-radius: 5px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover    {{ background-color: {self._BTN_HOVER}; }}
            QPushButton:pressed  {{ background-color: {self._BTN_PRESSED}; }}
            QPushButton:disabled {{ background-color: {self._BTN_DISABLED}; color: #666; }}
        """)
        self._gen_btn.clicked.connect(self._on_generate)
        layout.addWidget(self._gen_btn)

    # ------------------------------------------------------------------
    # Positioning & drag
    # ------------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        self.adjustSize()
        main_win = ui.get_main_window()
        if main_win:
            geo = main_win.geometry()
            x = geo.left() + (geo.width() * 2 // 3) - self.width() // 2
            y = geo.top() + geo.height() // 8
            self.move(x, y)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # ------------------------------------------------------------------
    # Status helper
    # ------------------------------------------------------------------

    def _set_status(self, html: str):
        self._status_lbl.setText(html)
        self._status_lbl.show()
        self.adjustSize()

    # ------------------------------------------------------------------
    # Logic
    # ------------------------------------------------------------------

    def _on_generate(self):
        if not project.is_open():
            self._set_status('<font color="#cc4444">No project open.</font>')
            return

        col = self._collection
        group = find_collection_group(col.name)
        if group is None:
            self._set_status(
                f'<font color="#cc4444">No group "{col.name}" found in stack. '
                f'Generate it via Manage first.</font>'
            )
            return

        if find_spsm(col.name) is not None:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Overwrite Smart Material?",
                f"A Smart Material already exists for \"{col.name}\".\n\nOverwrite it?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return
            dest_folder = get_collection_folder(col.name)
            for old_file in dest_folder.glob("*.spsm"):
                try:
                    old_file.unlink()
                except OSError:
                    pass

        self._gen_btn.setEnabled(False)
        self._set_status('<font color="gray"><i>Saving…</i></font>')
        QtWidgets.QApplication.processEvents()

        try:
            dest = save_as_smart_material(col.name, group)
        except Exception as e:
            self._set_status(f'<font color="#cc4444">&#10006; {e}</font>')
            logging.error(f"VG Collections: CollectionSetupFloater save failed: {e}")
            self._gen_btn.setEnabled(True)
            return

        self._saved = True
        self._set_status(
            f'<font color="#55aa55">&#10003; Saved.</font> '
            f'<font color="gray">{dest.name}</font>'
        )
        self._gen_btn.setEnabled(True)
        self.collection_saved.emit()
        self.close()

    def closeEvent(self, event):
        if self._saved:
            event.accept()
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            "Save Collection?",
            "Save the collection as a Smart Material before closing?",
            QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Cancel,
        )
        if reply == QtWidgets.QMessageBox.Save:
            event.ignore()
            self._on_generate()
        elif reply == QtWidgets.QMessageBox.Discard:
            event.accept()
        else:
            event.ignore()


# ---------------------------------------------------------------------------
# CollectionRowWidget — one row in the flat collections list
# ---------------------------------------------------------------------------

class CollectionRowWidget(QtWidgets.QFrame):
    """
    A single row representing one collection in the panel:

      [color dots]  [name (bold)]          [Load]  [Manage]  [✕]
                    [N slots · author · SM]

    Signals
    -------
    load_requested(Collection)    — user clicked Load
    manage_requested(Collection)  — user clicked Manage
    delete_requested(Collection)  — user clicked ✕
    """

    load_requested      = QtCore.Signal(object)
    manage_requested    = QtCore.Signal(object)
    duplicate_requested = QtCore.Signal(object)
    delete_requested    = QtCore.Signal(object)

    _MAX_DOTS = 6
    _BTN_SIZE = 26   # square icon button side length

    def __init__(self, collection: Collection, parent=None):
        super().__init__(parent)
        self._collection = collection
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.setFrameShadow(QtWidgets.QFrame.Plain)
        self._build_ui()

    @staticmethod
    def _icon_btn(symbol: str, tooltip: str) -> QtWidgets.QToolButton:
        """Return a small square button showing a unicode symbol."""
        btn = QtWidgets.QToolButton()
        btn.setText(symbol)
        btn.setFixedSize(CollectionRowWidget._BTN_SIZE, CollectionRowWidget._BTN_SIZE)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip(tooltip)
        btn.setStyleSheet("font-size: 13px; padding: 0px;")
        return btn

    def _build_ui(self):
        outer = QtWidgets.QHBoxLayout(self)
        outer.setContentsMargins(6, 5, 6, 5)
        outer.setSpacing(5)

        # Color dots
        dots_layout = QtWidgets.QHBoxLayout()
        dots_layout.setContentsMargins(0, 0, 0, 0)
        dots_layout.setSpacing(2)
        for slot in self._collection.slots[:self._MAX_DOTS]:
            dot = QtWidgets.QLabel()
            dot.setFixedSize(10, 10)
            pix = QtGui.QPixmap(10, 10)
            pix.fill(_color_to_qcolor(slot.color))
            dot.setPixmap(pix)
            dot.setToolTip(slot.material_name)
            dots_layout.addWidget(dot)
        if len(self._collection.slots) > self._MAX_DOTS:
            extra = QtWidgets.QLabel(f"+{len(self._collection.slots) - self._MAX_DOTS}")
            extra.setStyleSheet("color: gray; font-size: 9px;")
            dots_layout.addWidget(extra)
        outer.addLayout(dots_layout)

        # Name + subtitle
        info_layout = QtWidgets.QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(1)

        name_lbl = QtWidgets.QLabel(f"<b>{self._collection.name}</b>")
        name_lbl.setTextFormat(Qt.RichText)
        info_layout.addWidget(name_lbl)

        n = len(self._collection.slots)
        has_spsm = find_spsm(self._collection.name) is not None
        parts = [f"{n} slot{'s' if n != 1 else ''}"]
        if self._collection.author:
            parts.append(self._collection.author)
        subtitle = " · ".join(parts)
        sm_color = "#55aa55" if has_spsm else "gray"
        sm_text  = "SM ✓" if has_spsm else "SM ✗"
        sub_lbl = QtWidgets.QLabel(
            f'<span style="color: gray; font-size: 10px;">{subtitle}</span>'
            f'  <span style="color: {sm_color}; font-size: 10px;">{sm_text}</span>'
        )
        sub_lbl.setTextFormat(Qt.RichText)
        info_layout.addWidget(sub_lbl)

        outer.addLayout(info_layout, 1)

        # Icon buttons  ▶ = Load   ⚙ = Manage   ⧉ = Duplicate   ✕ = Delete
        self._load_btn = self._icon_btn("▶", "Insert Smart Material into the active layer stack")
        self._load_btn.clicked.connect(lambda: self.load_requested.emit(self._collection))
        outer.addWidget(self._load_btn)

        manage_btn = self._icon_btn("⚙", "Edit settings and run Painter operations")
        manage_btn.clicked.connect(lambda: self.manage_requested.emit(self._collection))
        outer.addWidget(manage_btn)

        dup_btn = self._icon_btn("⧉", "Duplicate this collection")
        dup_btn.clicked.connect(lambda: self.duplicate_requested.emit(self._collection))
        outer.addWidget(dup_btn)

        del_btn = self._icon_btn("✕", "Delete this collection")
        del_btn.setStyleSheet("font-size: 13px; padding: 0px; color: #cc4444;")
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self._collection))
        outer.addWidget(del_btn)

        # Load button enabled state
        if not has_spsm:
            self._load_btn.setEnabled(False)
            self._load_btn.setToolTip("No Smart Material saved — use ⚙ Manage → Save as Smart Material first")
        elif not project.is_open():
            self._load_btn.setEnabled(False)
            self._load_btn.setToolTip("Open a Painter project first")


# ---------------------------------------------------------------------------
# CollectionPanel — flat dockable panel
# ---------------------------------------------------------------------------

class CollectionPanel(QtWidgets.QWidget):
    """
    Dockable panel showing all collections as a flat, scrollable list.

    Each row has inline [Load] [Manage] [✕] buttons.
    A [+ New Collection] button sits at the bottom of the panel.

    Register with Painter via::

        dock = substance_painter.ui.add_dock_widget(CollectionPanel())
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("VG Collections")
        self.setObjectName("vg_collections_panel")
        self.setMinimumSize(300, 240)
        self._setup_floater = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Scrollable list of rows
        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

        self._rows_container = QtWidgets.QWidget()
        self._rows_layout = QtWidgets.QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(4)
        self._rows_layout.addStretch()

        self._scroll.setWidget(self._rows_container)
        root.addWidget(self._scroll, 1)

        # Empty-state label (shown when there are no collections)
        self._empty_lbl = QtWidgets.QLabel(
            "<i>No collections yet.<br>"
            "Click <b>+ New Collection</b> to create one.</i>"
        )
        self._empty_lbl.setTextFormat(Qt.RichText)
        self._empty_lbl.setAlignment(Qt.AlignCenter)
        self._empty_lbl.setStyleSheet("color: gray; padding: 24px;")
        root.addWidget(self._empty_lbl)

        # Bottom bar
        bottom = QtWidgets.QHBoxLayout()
        bottom.addStretch()
        new_btn = QtWidgets.QPushButton("+ New Collection")
        new_btn.clicked.connect(self._on_new)
        bottom.addWidget(new_btn)
        root.addLayout(bottom)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self):
        """Reload all collections from disk and rebuild the row list."""
        # Remove all existing row widgets (everything except the trailing stretch)
        while self._rows_layout.count() > 1:
            item = self._rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        collections = vg_collection.list_collections()

        if collections:
            self._empty_lbl.hide()
            self._scroll.show()
            for col in collections:
                row = CollectionRowWidget(col)
                row.load_requested.connect(self._on_load)
                row.manage_requested.connect(self._on_manage)
                row.duplicate_requested.connect(self._on_duplicate)
                row.delete_requested.connect(self._on_delete)
                self._rows_layout.insertWidget(self._rows_layout.count() - 1, row)
        else:
            self._scroll.hide()
            self._empty_lbl.show()

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _on_new(self):
        dlg = CollectionEditorDialog(parent=self)
        if dlg.exec() != QtWidgets.QDialog.Accepted:
            return

        col = dlg.result_collection()
        try:
            vg_collection.save_collection(col)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Save Error", str(e))
            return

        self.refresh()

        if not project.is_open():
            return

        try:
            builder = CollectionLayerBuilder()
            builder.build(col)
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, "Generate Error",
                f"Collection saved but layer structure could not be generated:\n{e}"
            )
            return

        if self._setup_floater is not None:
            self._setup_floater.close()
        self._setup_floater = CollectionSetupFloater(col)
        self._setup_floater.destroyed.connect(lambda: setattr(self, "_setup_floater", None))
        self._setup_floater.collection_saved.connect(self.refresh)
        self._setup_floater.show()

    def _on_manage(self, collection: Collection):
        dlg = CollectionManageDialog(collection, parent=self)
        if dlg.exec() != QtWidgets.QDialog.Accepted:
            return

        updated  = dlg.result_collection()
        old_name = dlg.old_name

        # Save metadata (renames folder if name changed, copies .spsm across)
        try:
            vg_collection.rename_collection(old_name, updated)
        except PermissionError as e:
            QtWidgets.QMessageBox.warning(self, "Cannot Rename", str(e))
            return
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Save Error", str(e))
            return

        self.refresh()

    def _on_duplicate(self, collection: Collection):
        default_name = f"{collection.name} (copy)"
        new_name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Duplicate Collection",
            "Name for the duplicate:",
            text=default_name,
        )
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()
        try:
            vg_collection.duplicate_collection(collection.name, new_name)
        except ValueError as e:
            QtWidgets.QMessageBox.warning(self, "Cannot Duplicate", str(e))
            return
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Duplicate Error", str(e))
            return
        self.refresh()

    def _on_load(self, collection: Collection):
        if not project.is_open():
            QtWidgets.QMessageBox.warning(self, "No Project", "Please open a project in Painter first.")
            return

        spsm_path = find_spsm(collection.name)
        if not spsm_path:
            QtWidgets.QMessageBox.warning(
                self, "File Not Found",
                f"No .spsm file found for '{collection.name}'.\n"
                "Use Manage → Save as Smart Material first."
            )
            return

        # Use the file's modification time as a suffix so that Painter creates
        # a fresh project resource when the .spsm has been updated on disk.
        # Without this, import_project_resource returns its cached version for
        # a resource that was already imported under the same name.
        mtime_tag = int(spsm_path.stat().st_mtime)
        import_name = f"{collection.name}_{mtime_tag}"

        try:
            imported = resource.import_project_resource(
                str(spsm_path),
                resource.Usage.SMART_MATERIAL,
                name=import_name,
                group="VG Collections",
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Import Error", str(e))
            logging.error(f"VG Collections: Smart Material import failed: {e}")
            return

        try:
            stack = textureset.get_active_stack()
            position = layerstack.InsertPosition.from_textureset_stack(stack)
            group = layerstack.insert_smart_material(position, imported.identifier())
            # The group inherits the import name (which includes the mtime suffix).
            # Rename it back to the clean collection name.
            group.set_name(collection.name)
        except Exception as e:
            resource.show_resources_in_ui([imported])
            QtWidgets.QMessageBox.warning(
                self, "Inserted to Shelf",
                f"Imported but could not insert into stack: {e}\n\n"
                "The Smart Material is highlighted in your Assets shelf — drag it manually."
            )
            logging.warning(f"VG Collections: insert_smart_material failed: {e}")

    def _on_delete(self, collection: Collection):
        reply = QtWidgets.QMessageBox.question(
            self,
            "Delete Collection",
            f"Delete '{collection.name}'? This cannot be undone.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            try:
                vg_collection.delete_collection(collection.name)
            except PermissionError:
                vg_collection.mark_for_deletion(collection.name)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Delete Error", str(e))
                return
            self.refresh()

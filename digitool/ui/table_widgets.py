"""
ui/table_widgets.py
Shared editable 1D table widget and CorrectionTabBase used by all correction tabs.
Each tab has a TipPanel sidebar; clicking a table's title label updates the tip.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor, QBrush

from digitool.rom_profiles import MapDef
from digitool.ui.map_tips import TipPanel


def heat_color(val: int, lo: int, hi: int) -> QColor:
    if hi == lo:
        return QColor("#1a2332")
    t = max(0.0, min(1.0, (val - lo) / (hi - lo)))
    if t < 0.5:
        u = t / 0.5
        return QColor(0, int(u * 200), int(100 + u * 155))
    else:
        u = (t - 0.5) / 0.5
        return QColor(int(u * 255), int(200 - u * 200), 0)


class Table1D(QWidget):
    """
    Editable 1D (or flat 2D) table. Clicking the title label emits
    _on_title_clicked so the parent tab can update the TipPanel.
    """

    def __init__(self, map_def: MapDef, parent=None):
        super().__init__(parent)
        self._map_def = map_def
        self._rom: bytearray | None = None
        self._title_clicked_cb = None   # set by CorrectionTabBase after creation

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(2)

        # Clickable title label
        lbl = QLabel(map_def.name)
        lbl.setStyleSheet(
            "color: #bccdd8; font-size: 11px; font-weight: bold;"
            "padding: 2px 0px;"
        )
        lbl.setCursor(Qt.PointingHandCursor)
        lbl.mousePressEvent = lambda _: self._fire_title_click()
        root.addWidget(lbl)

        addr_lbl = QLabel(f"@ 0x{map_def.data_addr:04X}  ·  {map_def.cols}×{map_def.rows}")
        addr_lbl.setStyleSheet("color: #3d5068; font-size: 10px; font-family: Consolas;")
        root.addWidget(addr_lbl)

        self.table = QTableWidget(map_def.rows, map_def.cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(map_def.rows > 1)
        self.table.setMinimumHeight(26 + map_def.rows * 28 + 8)
        self.table.setMaximumHeight(26 + map_def.rows * 28 + 8)
        self.table.setFont(QFont("Consolas", 10))
        root.addWidget(self.table)

        self.table.itemChanged.connect(self._on_item_changed)

    def _fire_title_click(self):
        if self._title_clicked_cb:
            self._title_clicked_cb(self._map_def.name)

    def load(self, rom: bytearray):
        self._rom = rom
        md = self._map_def
        data = [rom[md.data_addr + i] if md.data_addr + i < len(rom) else 0
                for i in range(md.size)]
        lo, hi = min(data), max(data)
        self.table.blockSignals(True)
        for r in range(md.rows):
            for c in range(md.cols):
                val = data[r * md.cols + c]
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignCenter)
                item.setBackground(QBrush(heat_color(val, lo, hi)))
                item.setForeground(QBrush(QColor("#e0eaf2")))
                self.table.setItem(r, c, item)
        self.table.blockSignals(False)

    def _on_item_changed(self, item: QTableWidgetItem):
        if self._rom is None:
            return
        try:
            val = int(item.text())
        except ValueError:
            self._revert_cell(item)
            return
        if not (0 <= val <= 255):
            self._revert_cell(item)
            return
        r, c = item.row(), item.column()
        offset = self._map_def.data_addr + r * self._map_def.cols + c
        if offset < len(self._rom):
            self._rom[offset] = val
        all_vals = [self._rom[self._map_def.data_addr + i]
                    for i in range(self._map_def.size)]
        lo, hi = min(all_vals), max(all_vals)
        self.table.blockSignals(True)
        item.setBackground(QBrush(heat_color(val, lo, hi)))
        item.setForeground(QBrush(QColor("#e0eaf2")))
        self.table.blockSignals(False)

    def _revert_cell(self, item: QTableWidgetItem):
        if self._rom is None:
            return
        r, c = item.row(), item.column()
        offset = self._map_def.data_addr + r * self._map_def.cols + c
        if offset < len(self._rom):
            self.table.blockSignals(True)
            item.setText(str(self._rom[offset]))
            self.table.blockSignals(False)

    def write_back(self, rom: bytearray) -> bytearray:
        md = self._map_def
        self.table.blockSignals(True)
        for r in range(md.rows):
            for c in range(md.cols):
                it = self.table.item(r, c)
                if it is None:
                    continue
                try:
                    val = max(0, min(255, int(it.text())))
                except ValueError:
                    continue
                offset = md.data_addr + r * md.cols + c
                if offset < len(rom):
                    rom[offset] = val
        self.table.blockSignals(False)
        return rom


class CorrectionTabBase(QWidget):
    """
    Base class for all correction tabs.
    Left side: scrollable column of Table1D widgets.
    Right side: TipPanel — updated when a table title is clicked.
    First table's tip is shown automatically on ROM load.
    """

    _MAP_NAMES: list[str] = []

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tables: list[Table1D] = []
        self._rom: bytearray | None = None

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left: scrollable tables ───────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._content = QWidget()
        self._col = QVBoxLayout(self._content)
        self._col.setContentsMargins(12, 12, 8, 12)
        self._col.setSpacing(14)
        scroll.setWidget(self._content)

        root.addWidget(scroll, 1)

        # ── Divider ───────────────────────────────────────────────────────────
        div = QFrame()
        div.setFrameShape(QFrame.VLine)
        div.setStyleSheet("color: #1a2332;")
        root.addWidget(div)

        # ── Right: tip panel ──────────────────────────────────────────────────
        self._tip_panel = TipPanel()
        root.addWidget(self._tip_panel)

        self._show_placeholder("No ROM loaded.")

    def _show_placeholder(self, msg: str):
        self._clear_col()
        lbl = QLabel(msg)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color: #3d5068; font-size: 13px;")
        lbl.setWordWrap(True)
        self._col.addWidget(lbl)
        self._col.addStretch()

    def _clear_col(self):
        self._tables = []
        while self._col.count():
            item = self._col.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_tip_requested(self, map_name: str):
        self._tip_panel.show_tip(map_name)

    def load_rom(self, result, rom: bytearray):
        self._rom = rom
        self._clear_col()

        if result.is_mk2:
            self._show_placeholder(
                "G40 Mk2 — correction map addresses not yet confirmed."
            )
            return

        map_lookup = {m.name: m for m in result.maps}
        found = [map_lookup[n] for n in self._MAP_NAMES if n in map_lookup]

        if not found:
            self._show_placeholder("No tables available for this variant.")
            return

        for md in found:
            t = Table1D(md)
            t._title_clicked_cb = self._on_tip_requested
            t.load(rom)
            self._tables.append(t)
            self._col.addWidget(t)

        self._col.addStretch()

        # Show tip for first table by default
        if self._tables:
            self._tip_panel.show_tip(self._tables[0]._map_def.name)

    def write_back(self, rom: bytearray) -> bytearray:
        for t in self._tables:
            rom = t.write_back(rom)
        return rom

"""
ui/main_window.py
Main application window — assembles all tabs and handles ROM file I/O.
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QTabWidget,
    QStatusBar, QLabel, QFileDialog, QMessageBox,
    QSizePolicy, QHBoxLayout
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor

from digitool.version import WINDOW_TITLE, APP_VERSION
from digitool.rom_profiles import detect_rom, DetectionResult

from digitool.ui.overview_tab    import OverviewTab
from digitool.ui.map_editor_tab  import MapEditorTab
from digitool.ui.corrections_tab import CorrectionsTab
from digitool.ui.hex_tab         import HexTab
from digitool.ui.diff_tab        import DiffTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumSize(1280, 800)
        self.resize(1440, 900)

        self._rom_path: str | None     = None
        self._rom:      bytearray | None = None
        self._result:   DetectionResult | None = None

        self._build_ui()
        self._setup_status_bar()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header bar
        header = QWidget()
        header.setFixedHeight(42)
        header.setStyleSheet("background: #0d1117; border-bottom: 1px solid #1a2332;")
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(16, 0, 16, 0)

        logo = QLabel(f"DigiTool")
        logo.setFont(QFont("Segoe UI", 14, QFont.Bold))
        logo.setStyleSheet("color: #00d4ff; letter-spacing: 2px;")

        ver_lbl = QLabel(f"v{APP_VERSION}")
        ver_lbl.setStyleSheet("color: #3d5068; font-size: 11px; margin-left: 8px;")

        sub_lbl = QLabel("Digifant 1  ·  G60 / G40  ECU Editor")
        sub_lbl.setStyleSheet("color: #3d5068; font-size: 11px; margin-left: 16px;")

        self.lbl_rom_name = QLabel("No ROM loaded")
        self.lbl_rom_name.setStyleSheet("color: #3d5068; font-size: 11px; font-family: Consolas;")

        hlay.addWidget(logo)
        hlay.addWidget(ver_lbl)
        hlay.addWidget(sub_lbl)
        hlay.addStretch()
        hlay.addWidget(self.lbl_rom_name)

        root.addWidget(header)

        # Tab area
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.tab_overview    = OverviewTab()
        self.tab_maps        = MapEditorTab()
        self.tab_corrections = CorrectionsTab()
        self.tab_hex         = HexTab()
        self.tab_diff        = DiffTab()

        self.tabs.addTab(self.tab_overview,    "Overview")
        self.tabs.addTab(self.tab_maps,        "Maps")
        self.tabs.addTab(self.tab_corrections, "Corrections")
        self.tabs.addTab(self.tab_hex,         "Hex View")
        self.tabs.addTab(self.tab_diff,        "Compare")

        root.addWidget(self.tabs, 1)

        # Wire overview signals
        self.tab_overview.sig_open_rom.connect(self._open_rom)
        self.tab_overview.sig_save_rom.connect(self._save_rom)
        self.tab_overview.sig_save_as.connect(self._save_as)
        self.tab_overview.sig_rom_mutated.connect(self._on_rom_mutated)

        # Enable drag-and-drop of .BIN files onto the window
        self.setAcceptDrops(True)

    def _setup_status_bar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.setStyleSheet(
            "QStatusBar { background: #0d1117; color: #3d5068; "
            "border-top: 1px solid #1a2332; font-size: 11px; }"
        )
        self.lbl_status = QLabel("Ready")
        self.statusbar.addPermanentWidget(self.lbl_status)
        self.statusbar.showMessage(f"DigiTool v{APP_VERSION}  —  Digifant 1 G60/G40 ECU Editor")

    # ── ROM I/O ───────────────────────────────────────────────────────────────

    def _open_rom(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open ROM File", "", "BIN Files (*.bin *.BIN);;All Files (*)"
        )
        if not path:
            return

        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as e:
            QMessageBox.critical(self, "Error", f"Could not read file:\n{e}")
            return

        if len(data) != 0x8000:
            QMessageBox.warning(
                self, "Wrong Size",
                f"Expected 32768 bytes (32KB), got {len(data):,} bytes.\n"
                f"Only 27C256 EPROM dumps are supported."
            )
            return

        self._load_rom_data(path, bytes(data))

    def _load_rom_data(self, path: str, data: bytes):
        result = detect_rom(data)
        self._rom_path = path
        self._rom      = bytearray(data)
        self._result   = result

        short = path.split("/")[-1].split("\\")[-1]
        self.lbl_rom_name.setText(f"{short}  ·  {result.label}")
        self.lbl_rom_name.setStyleSheet("color: #bccdd8; font-size: 11px; font-family: Consolas;")

        # Warnings
        if result.warnings:
            msg = "\n".join(result.warnings)
            QMessageBox.information(self, "ROM Detection", msg)

        # Populate all tabs
        self.tab_overview.update_rom(result, self._rom)
        self.tab_maps.load_rom(result, self._rom)
        self.tab_corrections.load_rom(result, self._rom)
        self.tab_hex.load_rom(result, self._rom)
        self.tab_diff.set_rom_a(result, self._rom)

        self.statusbar.showMessage(
            f"Loaded: {short}  |  {result.label}  |  {result.confidence} confidence  |  CRC32: {result.crc32:#010x}",
            8000
        )
        # Switch to maps tab after load
        self.tabs.setCurrentWidget(self.tab_maps)

    def _save_rom(self):
        if self._rom is None or self._rom_path is None:
            return
        # Write back pending map edits
        self._rom = bytearray(self.tab_maps.write_back())
        try:
            with open(self._rom_path, "wb") as f:
                f.write(self._rom)
            self.statusbar.showMessage(f"Saved: {self._rom_path}", 4000)
        except OSError as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def _save_as(self):
        if self._rom is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save ROM As", "", "BIN Files (*.bin *.BIN);;All Files (*)"
        )
        if not path:
            return
        self._rom = bytearray(self.tab_maps.write_back())
        try:
            with open(path, "wb") as f:
                f.write(self._rom)
            self._rom_path = path
            self.statusbar.showMessage(f"Saved as: {path}", 4000)
        except OSError as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def _on_rom_mutated(self, new_rom):
        """Called when overview tab writes rev limit or patches in-place."""
        self._rom = bytearray(new_rom)

    # ── Drag and drop ─────────────────────────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(u.toLocalFile().lower().endswith(".bin") for u in urls):
                event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".bin"):
                try:
                    with open(path, "rb") as f:
                        data = f.read()
                    if len(data) == 0x8000:
                        self._load_rom_data(path, data)
                    else:
                        QMessageBox.warning(
                            self, "Wrong Size",
                            f"Expected 32 KB, got {len(data):,} bytes."
                        )
                except OSError as e:
                    QMessageBox.critical(self, "Error", str(e))
                break

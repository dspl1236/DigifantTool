"""
ui/main_window.py
Main application window — assembles all tabs and handles ROM file I/O.
"""

import os

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QTabWidget,
    QStatusBar, QLabel, QFileDialog, QMessageBox,
    QHBoxLayout, QAction, QDialog, QDialogButtonBox,
)
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QFont

from digitool.version import WINDOW_TITLE, APP_VERSION
from digitool.rom_profiles import (
    detect_rom, detect_rom_all, normalize_rom_image, DetectionResult,
)
from digitool.immo_patches import (
    PATCH_DB, find_patch, find_patches_for_ecu, check_already_patched,
    apply_patch, verify_patch_location, ImmoPatchError,
)
from digitool.kwp import (
    KWPMonitor, LiveValues,
    kwpbridge_available, kwpbridge_running,
    status_label, live_summary,
)

from digitool.ui.overview_tab    import OverviewTab
from digitool.ui.map_editor_tab  import MapPanel
from digitool.ui.boost_tab       import BoostTab
from digitool.ui.wot_accel_tab   import WotAccelTab
from digitool.ui.knock_dwell_tab import KnockDwellTab
from digitool.ui.idle_ign_tab    import IdleIgnTab
from digitool.ui.temperature_tab import TemperatureTab
from digitool.ui.lambda_tab      import LambdaTab
from digitool.ui.hex_tab         import HexTab
from digitool.ui.diff_tab        import DiffTab
from digitool.ui.immo_tab        import ImmoTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumSize(1280, 800)
        self.resize(1440, 900)

        self._rom_path: str | None          = None
        self._rom:      bytearray | None    = None
        self._result:   DetectionResult | None = None

        # Map panels — populated per ROM load (variable count for triple-map)
        self._map_panels: list[MapPanel] = []
        # Correction tabs — fixed instances, all share write_back interface
        self._corr_tabs: list = []

        # ── KWPBridge live overlay ────────────────────────────────────────────
        self._kwp_monitor = KWPMonitor(self)
        self._kwp_matched  = False
        self._kwp_monitor.connected.connect(self._on_kwp_connected)
        self._kwp_monitor.disconnected.connect(self._on_kwp_disconnected)
        self._kwp_monitor.live_data.connect(self._on_kwp_live_data)
        self._kwp_monitor.mismatch.connect(self._on_kwp_mismatch)

        self._build_ui()
        self._setup_status_bar()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_menu()
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

        logo = QLabel("DigiTool")
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

        # Main tab bar
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        root.addWidget(self.tabs, 1)

        # ── Fixed tabs (always present) ──────────────────────────────────────
        self.tab_overview    = OverviewTab()
        self.tab_boost       = BoostTab()
        self.tab_wot_accel   = WotAccelTab()
        self.tab_knock       = KnockDwellTab()
        self.tab_idle        = IdleIgnTab()
        self.tab_temperature = TemperatureTab()
        self.tab_lambda      = LambdaTab()
        self.tab_hex         = HexTab()
        self.tab_diff        = DiffTab()
        self.tab_immo        = ImmoTab()

        self._corr_tabs = [
            self.tab_boost, self.tab_wot_accel, self.tab_knock,
            self.tab_idle, self.tab_temperature, self.tab_lambda,
        ]

        # Add permanent tabs (map tabs inserted dynamically on ROM load)
        self.tabs.addTab(self.tab_overview, "Overview")
        # Map tabs added at indices 1..N dynamically — see _rebuild_map_tabs()
        self._map_tab_count = 0   # tracks how many map tabs are currently inserted

        # Correction tabs — added after map tabs
        self._corr_tab_start = 1  # updated in _rebuild_map_tabs

        self.tabs.addTab(self.tab_boost,       "Boost / ISV")
        self.tabs.addTab(self.tab_wot_accel,   "WOT & Accel")
        self.tabs.addTab(self.tab_knock,       "Knock & Dwell")
        self.tabs.addTab(self.tab_idle,        "Idle & Ign")
        self.tabs.addTab(self.tab_temperature, "Temperature")
        self.tabs.addTab(self.tab_lambda,      "Lambda / OXS")
        self.tabs.addTab(self.tab_hex,         "Hex View")
        self.tabs.addTab(self.tab_diff,        "Compare")
        self.tabs.addTab(self.tab_immo,        "Immo")

        # Wire overview signals
        self.tab_overview.sig_open_rom.connect(self._open_rom)
        self.tab_overview.sig_save_rom.connect(self._save_rom)
        self.tab_overview.sig_save_as.connect(self._save_as)
        self.tab_overview.sig_save_512.connect(self._save_27c512)
        self.tab_overview.sig_rom_mutated.connect(self._on_rom_mutated)
        self.tab_immo.sig_rom_mutated.connect(self._on_rom_mutated)

        self.setAcceptDrops(True)

    def _build_menu(self):
        mb = self.menuBar()
        mb.setStyleSheet(
            "QMenuBar { background: #0d1117; color: #8b9cb0; }"
            "QMenuBar::item:selected { background: #1a2332; }"
            "QMenu { background: #0d1117; color: #8b9cb0; border: 1px solid #1a2332; }"
            "QMenu::item:selected { background: #1a2332; }")

        # ── File ─────────────────────────────────────────────────────────────
        fm = mb.addMenu("File")
        for label, slot in [
            ("Open ROM…",        self._open_rom),
            ("Save ROM",         self._save_rom),
            ("Save As…",         self._save_as),
            ("Save 27C512 .bin…",self._save_27c512),
        ]:
            a = QAction(label, self)
            a.triggered.connect(slot)
            fm.addAction(a)
        fm.addSeparator()
        fm.addAction("Quit", self.close)

        # ── Tools ─────────────────────────────────────────────────────────────
        tm = mb.addMenu("Tools")

        self._act_kwp_status = QAction("KWPBridge: not running", self)
        self._act_kwp_status.setEnabled(False)
        tm.addAction(self._act_kwp_status)
        tm.addSeparator()

        a = QAction("Live Data Connection…", self)
        a.setShortcut("Ctrl+K")
        a.triggered.connect(self._show_kwp_dialog)
        tm.addAction(a)

        act_dash = QAction("Dashboard…", self)
        act_dash.setShortcut("Ctrl+D")
        act_dash.triggered.connect(self._toggle_dashboard)
        tm.addAction(act_dash)

        self._kwp_menu_timer = QTimer(self)
        self._kwp_menu_timer.timeout.connect(self._refresh_kwp_menu_label)
        self._kwp_menu_timer.start(2000)

        # ── Help ─────────────────────────────────────────────────────────────
        hm = mb.addMenu("Help")
        hm.addAction("About DigiTool", self._on_about)

    def _on_about(self):
        QMessageBox.about(self, "DigiTool",
                          f"<b>DigiTool</b>  v{APP_VERSION}<br><br>"
                          "Digifant 1  ·  G60 / G40  ECU Editor<br><br>"
                          "Supports: VW Golf G60  ·  Golf G40  ·  Corrado G60<br>"
                          "Scirocco 16v  ·  Golf G60 Limited")

    def _refresh_kwp_menu_label(self):
        if not hasattr(self, '_act_kwp_status'):
            return
        if not kwpbridge_available():
            self._act_kwp_status.setText("KWPBridge: not installed")
        elif kwpbridge_running():
            pn = self._kwp_monitor.current_pn()
            if pn:
                self._act_kwp_status.setText(f"KWPBridge: connected  ·  {pn}")
            else:
                self._act_kwp_status.setText("KWPBridge: running — no ECU")
        else:
            self._act_kwp_status.setText("KWPBridge: not running")

    def _show_kwp_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Live Data — KWPBridge Connection")
        dlg.setMinimumWidth(420)
        dlg.setStyleSheet("background: #0d1117; color: #8b9cb0;")

        from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout
        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)

        if not kwpbridge_available():
            dot, body = "⚫", (
                "<b>KWPBridge is not installed.</b><br><br>"
                "DigiTool works fully standalone without it.<br><br>"
                "KWPBridge adds optional live ECU data overlay:<br>"
                "• Real-time RPM, load, coolant on map tables<br>"
                "• Lambda voltage and ignition timing readouts<br>"
                "• Part-number safety gate before ROM writes<br><br>"
                "Run KWPBridge alongside DigiTool and connect<br>"
                "a KL-line interface to your ECU.")
        elif kwpbridge_running():
            pn = self._kwp_monitor.current_pn()
            rom_pn = self._result.part_number if self._result else ""
            if pn:
                dot = "🟢" if self._kwp_matched else "🟡"
                if self._kwp_matched:
                    body = (f"<b>KWPBridge connected.</b><br><br>"
                            f"ECU: <b>{pn}</b><br>"
                            "ECU matches loaded ROM — live overlay active.")
                else:
                    body = (f"<b>KWPBridge connected.</b><br><br>"
                            f"ECU: <b>{pn}</b><br>"
                            f"ROM: <b>{rom_pn or '(none loaded)'}</b><br>"
                            "Load the matching ROM to enable overlay.")
            else:
                dot  = "🟡"
                body = ("<b>KWPBridge running — no ECU detected.</b><br><br>"
                        "Connect KL-line interface and turn ignition on.")
        else:
            dot  = "🔴"
            body = ("<b>KWPBridge is installed but not running.</b><br><br>"
                    "DigiTool is fully operational without it.<br><br>"
                    "Start KWPBridge to enable live data overlay.<br>"
                    "Auto-detected within 2 seconds of starting.")

        icon = QLabel(dot)
        icon.setStyleSheet("font-size: 28px;")
        msg = QLabel(body)
        msg.setWordWrap(True)
        row = QHBoxLayout()
        row.addWidget(icon)
        row.addWidget(msg, 1)
        w = QWidget()
        w.setLayout(row)
        lay.addWidget(w)
        bb = QDialogButtonBox(QDialogButtonBox.Ok)
        bb.accepted.connect(dlg.accept)
        lay.addWidget(bb)
        dlg.exec_()

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

    def _rebuild_map_tabs(self, result: DetectionResult, rom: bytearray):
        """
        Remove old map panels from the tab bar and insert fresh ones
        based on the loaded ROM family (single ign / triple ign + fuel).
        Map tabs always sit at indices 1..N (after Overview).
        """
        # Remove old map panel tabs
        for _ in range(self._map_tab_count):
            self.tabs.removeTab(1)  # always remove index 1 (Overview stays at 0)
        self._map_panels.clear()
        self._map_tab_count = 0

        maps = result.maps

        if result.is_triple:
            ign_defs = [m for m in maps if "Ignition" in m.name]
            tab_names = ["Ign Map 1", "Ign Map 2", "Ign Map 3"]
            titles    = ["Ignition — Low Load", "Ignition — Mid Load", "Ignition — WOT"]
        else:
            ign_defs  = [m for m in maps if m.name == "Ignition"]
            tab_names = ["Ignition"]
            titles    = ["Ignition"]

        fuel_defs = [m for m in maps if m.name == "Fuel"]

        insert_idx = 1
        for md, tab_name, title in zip(ign_defs, tab_names, titles):
            panel = MapPanel(title, "ign")
            panel.load(md, rom)
            self.tabs.insertTab(insert_idx, panel, tab_name)
            self._map_panels.append(panel)
            insert_idx += 1
            self._map_tab_count += 1

        for md in fuel_defs:
            panel = MapPanel("Fuel", "fuel")
            panel.load(md, rom)
            self.tabs.insertTab(insert_idx, panel, "Fuel")
            self._map_panels.append(panel)
            insert_idx += 1
            self._map_tab_count += 1

    # ── ROM I/O ───────────────────────────────────────────────────────────────

    def _open_rom(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open ROM File", "", "BIN Files (*.bin *.BIN);;All Files (*)"
        )
        if not path:
            return
        try:
            with open(path, "rb") as f:
                raw = f.read()
        except OSError as e:
            QMessageBox.critical(self, "Error", f"Could not read file:\n{e}")
            return

        data, notes = normalize_rom_image(raw)
        if notes:
            QMessageBox.information(
                self, "ROM Image Normalized",
                "\n".join(notes) + f"\n\nFile: {os.path.basename(path)}\nLoaded as: {len(data):,} bytes"
            )
        if len(data) != 0x8000:
            QMessageBox.critical(
                self, "Unsupported Size",
                f"Could not normalize to 32 KB.\nGot {len(data):,} bytes after processing."
            )
            return
        self._load_rom_data(path, bytes(data))

    def _load_rom_data(self, path: str, data: bytes):
        result = detect_rom_all(data)
        self._rom_path = path
        self._rom      = bytearray(data)
        self._result   = result

        short = os.path.basename(path)
        self.lbl_rom_name.setText(f"{short}  ·  {result.label}")
        self.lbl_rom_name.setStyleSheet("color: #bccdd8; font-size: 11px; font-family: Consolas;")

        if result.warnings:
            QMessageBox.information(self, "ROM Detection", "\n".join(result.warnings))

        # Rebuild dynamic map tabs
        self._rebuild_map_tabs(result, self._rom)

        # Load all fixed tabs
        self.tab_overview.update_rom(result, self._rom)
        for tab in self._corr_tabs:
            tab.load_rom(result, self._rom)
        self.tab_hex.load_rom(result, self._rom)
        self.tab_diff.set_rom_a(result, self._rom)
        self.tab_immo.load_rom(result, self._rom)

        self.statusbar.showMessage(
            f"Loaded: {short}  |  {result.label}  |  {result.confidence} confidence"
            f"  |  CRC32: {result.crc32:#010x}", 8000
        )

        # Tell KWP monitor what ROM is loaded — enables safety gate
        if result.part_number:
            self._kwp_monitor.set_rom_part_number(result.part_number)
            self._update_kwp_ui()

        # Jump to first ignition tab
        self.tabs.setCurrentIndex(1)

    # ── KWPBridge live overlay handlers ───────────────────────────────────────

    def _on_kwp_connected(self, ecu_pn: str):
        self._kwp_matched = self._kwp_monitor.is_matched()
        self._update_kwp_ui()
        if self._kwp_matched:
            for panel in self._map_panels:
                panel.attach_kwp()
            self.statusbar.showMessage(
                f"KWPBridge connected  ·  {ecu_pn}  ·  ECU matches ROM  ·  live overlay active")
        else:
            rom_pn = self._result.part_number if self._result else ""
            self.statusbar.showMessage(
                f"KWPBridge connected  ·  ECU {ecu_pn}  ≠  ROM {rom_pn}  ·  overlay locked")

    def _on_kwp_disconnected(self):
        self._kwp_matched = False
        for panel in self._map_panels:
            panel.detach_kwp()
        self._update_kwp_ui()
        self.statusbar.showMessage("KWPBridge disconnected")

    def _on_kwp_mismatch(self, ecu_pn: str, rom_pn: str):
        self._kwp_matched = False
        for panel in self._map_panels:
            panel.detach_kwp()
        self._update_kwp_ui()

    def _on_kwp_live_data(self, lv: LiveValues):
        if not self._kwp_matched:
            return
        for panel in self._map_panels:
            panel.update_overlay(lv)
        # Update overview KWP banner
        self._update_kwp_ui(lv)

    def _toggle_dashboard(self):
        """Open or close the live ECU dashboard window."""
        from digitool.kwp import DashboardWindow
        if not hasattr(self, '_dashboard') or self._dashboard is None:
            self._dashboard = DashboardWindow(self._kwp_monitor, parent=self)
        if self._dashboard.is_visible():
            self._dashboard.hide()
        else:
            self._dashboard.show()

    def _update_kwp_ui(self, lv: LiveValues = None):
        self._refresh_kwp_menu_label()
        rom_pn = self._result.part_number if self._result else ""
        text, colour = status_label(self._kwp_monitor, rom_pn)
        if lv and self._kwp_matched:
            summary = live_summary(lv)
            if summary:
                text = f"🟢  {self._kwp_monitor.current_pn()}  ·  {summary}"
        self.tab_overview.update_kwp_status(text, colour)

    def closeEvent(self, event):
        self._kwp_monitor.stop()
        event.accept()



    def _collect_rom(self) -> bytearray:
        """Collect all pending edits from every tab into a fresh bytearray."""
        if self._rom is None:
            return bytearray()
        rom = bytearray(self._rom)
        for panel in self._map_panels:
            rom = panel.write_back(rom)
        for tab in self._corr_tabs:
            rom = tab.write_back(rom)
        return rom

    def _save_rom(self):
        if self._rom is None:
            return

        # Suggest a filename: original stem + "_edited.bin"
        base = ""
        if self._rom_path:
            stem = os.path.splitext(os.path.basename(self._rom_path))[0]
            base = (stem + ".bin") if stem.endswith("_edited") else (stem + "_edited.bin")

        path, _ = QFileDialog.getSaveFileName(
            self, "Save 27C256 ROM (32 KB)", base,
            "BIN Files (*.bin *.BIN);;All Files (*)"
        )
        if not path:
            return

        self._rom = self._collect_rom()
        try:
            with open(path, "wb") as f:
                f.write(self._rom)
            self._rom_path = path
            short = os.path.basename(path)
            self.lbl_rom_name.setText(
                f"{short}  \u00b7  {self._result.label}" if self._result else short
            )
            self.statusbar.showMessage(f"Saved: {path}", 4000)
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
        self._rom = self._collect_rom()
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

    def _save_27c512(self):
        if self._rom is None:
            return
        rom_32k = bytes(self._collect_rom())
        if len(rom_32k) != 0x8000:
            QMessageBox.critical(self, "Error",
                f"ROM is {len(rom_32k):,} bytes — expected 32,768 bytes.\n"
                "Cannot create 27C512 image.")
            return

        base = ""
        if self._rom_path:
            stem = os.path.splitext(os.path.basename(self._rom_path))[0]
            base = stem + "_27C512.bin"

        path, _ = QFileDialog.getSaveFileName(
            self, "Save 27C512 Image (64 KB)", base,
            "BIN Files (*.bin *.BIN);;All Files (*)"
        )
        if not path:
            return

        image_64k = rom_32k + rom_32k
        try:
            with open(path, "wb") as f:
                f.write(image_64k)
            self.statusbar.showMessage(
                f"Saved 27C512 image: {path}  ({len(image_64k):,} bytes — 32KB × 2 mirror)", 6000
            )
            QMessageBox.information(self, "27C512 Image Saved",
                f"64 KB image written to:\n{path}\n\n"
                "Contents: 32 KB ROM mirrored twice.\n"
                "Ready to burn to a 27C512 EPROM.")
        except OSError as e:
            QMessageBox.critical(self, "Save Error", str(e))

    # ── Drag and drop ─────────────────────────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            if any(u.toLocalFile().lower().endswith(".bin")
                   for u in event.mimeData().urls()):
                event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".bin"):
                try:
                    with open(path, "rb") as f:
                        raw = f.read()
                    data, notes = normalize_rom_image(raw)
                    if notes:
                        QMessageBox.information(self, "ROM Image Normalized",
                            "\n".join(notes))
                    if len(data) == 0x8000:
                        self._load_rom_data(path, bytes(data))
                    else:
                        QMessageBox.warning(self, "Wrong Size",
                            f"Expected 32 KB, got {len(data):,} bytes.")
                except OSError as e:
                    QMessageBox.critical(self, "Error", str(e))
                break

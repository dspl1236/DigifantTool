"""
digitool/kwp.py — KWPBridge integration for DigiTool.

Same pattern as hachirom/kwp.py, adapted for Digifant 1 G60/G40:

  - Digifant ECUs report RPM in group 1 cell 1 (not group 0 cell 3)
  - No closed-loop lambda — O2S is a raw voltage (0-1.1V)
  - Load is VAF signal (raw 0-255), not calculated %
  - Ignition timing not directly readable on Digifant 1

KWPBridge workflow:
  1. Launch KWPBridge.exe → ⚙ Mock ECU → Digifant 1
  2. Open DigiTool → load G60 ROM
  3. KWP monitor detects KWPBridge on :50266
  4. Safety gate: ECU part number matches ROM variant
  5. Live overlay activates on ignition and fuel maps
"""

import logging
from typing import Optional

log = logging.getLogger(__name__)

# ── Optional imports ──────────────────────────────────────────────────────────

try:
    from kwpbridge.client import KWPClient, is_running as _kwp_is_running
    from kwpbridge.constants import DEFAULT_PORT
    _KWP_AVAILABLE = True
except ImportError:
    _KWP_AVAILABLE = False
    DEFAULT_PORT   = 50266

try:
    from PyQt5.QtCore import QObject, QTimer, pyqtSignal
    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False


def kwpbridge_available() -> bool:
    return _KWP_AVAILABLE


def kwpbridge_running() -> bool:
    if not _KWP_AVAILABLE:
        return False
    try:
        return _kwp_is_running(port=DEFAULT_PORT)
    except Exception:
        return False


# ── Live values from Digifant state dict ──────────────────────────────────────

class LiveValues:
    """
    Decoded Digifant 1 measuring block values from a KWPBridge state dict.

    Digifant 1 group 1 layout (sent as group "0" by mock server):
      cell 1 = Engine Speed       (RPM)
      cell 2 = Engine Load        (VAF signal, raw 0-255)
      cell 3 = Coolant Temp       (inverse NTC — lower = hotter)
      cell 4 = Injection Time     (ms)

    No closed-loop lambda — O2S voltage readable separately.
    """

    def __init__(self, state: dict):
        self.rpm:         Optional[float] = None
        self.load:        Optional[float] = None   # VAF raw 0-255
        self.load_pct:    Optional[float] = None   # approx % (load/255*100)
        self.coolant:     Optional[float] = None   # approx °C
        self.inj_time:    Optional[float] = None   # injection time (raw)
        self.o2s_voltage: Optional[float] = None   # O2S 0-1.1V (if available)
        self.o2s_rich:    Optional[bool]  = None   # True=rich, False=lean, None=unknown
        self.ecu_pn:      str = ""

        if not state or not state.get("connected"):
            return

        self.ecu_pn = state.get("ecu_id", {}).get("part_number", "")

        groups = state.get("groups", {})
        # Mock sends primary group as "0" regardless of Digifant convention
        group0 = groups.get("0", groups.get(0, {}))
        cells  = {c["index"]: c for c in group0.get("cells", [])}

        def _val(idx):
            c = cells.get(idx)
            return c["value"] if c else None

        # Detect layout: Digifant has RPM at cell 1, 7A has RPM at cell 3
        pn = self.ecu_pn.upper()
        is_digifant = (pn.startswith("037906") or pn.startswith("039906")
                       or not pn)  # unknown ECU — assume Digifant in DigiTool

        if is_digifant:
            self.rpm      = _val(1)
            self.load     = _val(2)
            self.coolant  = _val(3)   # already decoded to approx °C by mock
            self.inj_time = _val(4)
        else:
            # Fallback for Motronic — shouldn't happen in DigiTool
            self.rpm     = _val(3)
            self.load    = _val(2)
            self.coolant = _val(1)

        if self.load is not None:
            self.load_pct = (self.load / 255.0) * 100.0

        # O2S voltage from group 0 cell 5 if available
        # (only present when mock sends full group 0, not group 1)
        group0_raw = groups.get("0", groups.get(0, {}))
        if isinstance(group0_raw, dict):
            cells0 = {c["index"]: c for c in group0_raw.get("cells", [])}
            o2s_cell = cells0.get(5)
            if o2s_cell and o2s_cell.get("unit") == "V":
                self.o2s_voltage = o2s_cell["value"]
                # Binary switching: <0.45V = lean, >0.65V = rich
                if self.o2s_voltage is not None:
                    self.o2s_rich = self.o2s_voltage > 0.55

    @property
    def valid(self) -> bool:
        return self.rpm is not None

    def o2s_colour(self) -> str:
        """Colour for O2S state indicator."""
        if self.o2s_rich is None:
            return "#444444"
        return "#2dff6e" if self.o2s_rich else "#ff9900"   # green=rich, amber=lean

    def o2s_label(self) -> str:
        """Rich/lean/unknown string."""
        if self.o2s_rich is None:
            return "—"
        return "RICH" if self.o2s_rich else "LEAN"


# ── Qt monitor (only when Qt + kwpbridge available) ───────────────────────────

if _QT_AVAILABLE and _KWP_AVAILABLE:

    class KWPMonitor(QObject):
        """
        Qt wrapper around KWPClient for DigiTool.

        Signals
        -------
        connected(str)        — ECU part number on connect
        disconnected()
        live_data(LiveValues) — new state at poll rate
        mismatch(str, str)    — (ecu_pn, rom_pn) when mismatch
        """

        connected    = pyqtSignal(str)
        disconnected = pyqtSignal()
        live_data    = pyqtSignal(object)    # LiveValues
        mismatch     = pyqtSignal(str, str)

        def __init__(self, parent=None):
            super().__init__(parent)
            self._client:  KWPClient | None = None
            self._rom_pn:  str = ""
            self._matched  = False

            self._timer = QTimer(self)
            self._timer.timeout.connect(self._poll)
            self._timer.start(1000)

        def set_rom_part_number(self, pn: str):
            self._rom_pn = pn.upper().replace("-", "").strip()
            self._check_match()

        def stop(self):
            self._timer.stop()
            if self._client:
                try: self._client.disconnect()
                except Exception: pass
                self._client = None

        def is_matched(self) -> bool:
            return self._matched

        def current_pn(self) -> str:
            if self._client and self._client.state:
                return self._client.state.get(
                    "ecu_id", {}).get("part_number", "")
            return ""

        def _poll(self):
            if self._client and self._client.connected:
                state = self._client.state
                if state:
                    lv = LiveValues(state)
                    if lv.valid:
                        self.live_data.emit(lv)
                    self._check_match()
                return
            if kwpbridge_running():
                self._connect_client()

        def _connect_client(self):
            try:
                self._client = KWPClient(port=DEFAULT_PORT)
                self._client.on_connect(self._on_connect)
                self._client.on_disconnect(self._on_disconnect)
                self._client.on_state(self._on_state)
                self._client.connect(auto_reconnect=False)
            except Exception as e:
                log.debug(f"KWPMonitor connect error: {e}")
                self._client = None

        def _on_connect(self):
            pn = self.current_pn()
            log.info(f"KWPMonitor: connected, ECU={pn}")
            self.connected.emit(pn)
            self._check_match()

        def _on_disconnect(self):
            self._matched = False
            self.disconnected.emit()

        def _on_state(self, state: dict):
            lv = LiveValues(state)
            if lv.valid:
                self.live_data.emit(lv)
            self._check_match()

        def _check_match(self):
            if not self._client or not self._client.state:
                self._matched = False
                return
            ecu_pn = self.current_pn().upper().replace("-", "").strip()
            if not ecu_pn or not self._rom_pn:
                self._matched = False
                return
            new_match = (ecu_pn == self._rom_pn)
            if not new_match and ecu_pn:
                self.mismatch.emit(ecu_pn, self._rom_pn)
            self._matched = new_match

else:
    class _NoOpSignal:
        def connect(self, *a, **kw):    pass
        def disconnect(self, *a, **kw): pass
        def emit(self, *a, **kw):       pass

    class KWPMonitor:   # type: ignore
        connected    = _NoOpSignal()
        disconnected = _NoOpSignal()
        live_data    = _NoOpSignal()
        mismatch     = _NoOpSignal()

        def __init__(self, parent=None): pass
        def set_rom_part_number(self, pn): pass
        def stop(self): pass
        def is_matched(self) -> bool: return False
        def current_pn(self) -> str:  return ""


# ── Status helpers ────────────────────────────────────────────────────────────

def status_label(monitor: "KWPMonitor", rom_pn: str) -> tuple[str, str]:
    """Return (text, colour) for KWP status indicator."""
    if not _KWP_AVAILABLE:
        return "KWPBridge not installed", "#555555"
    if not kwpbridge_running():
        return "KWPBridge not running", "#555555"
    ecu_pn = monitor.current_pn() if monitor else ""
    if not ecu_pn:
        return "KWPBridge running — no ECU", "#ffaa00"
    if monitor and monitor.is_matched():
        return f"🟢  {ecu_pn}  ·  ECU matches ROM", "#2dff6e"
    return f"🟡  {ecu_pn}  ≠  {rom_pn}  ·  mismatch", "#ffaa00"


def live_summary(lv: "LiveValues") -> str:
    """One-line status string."""
    if lv is None or not lv.valid:
        return ""
    parts = []
    if lv.rpm      is not None: parts.append(f"{lv.rpm:.0f} RPM")
    if lv.coolant  is not None: parts.append(f"{lv.coolant:.0f}°C")
    if lv.load_pct is not None: parts.append(f"{lv.load_pct:.0f}% load")
    if lv.inj_time is not None: parts.append(f"{lv.inj_time/10:.1f}ms inj")
    return "  ·  ".join(parts)

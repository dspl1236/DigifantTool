"""
ui/map_tips.py
Tuning tip definitions and TipPanel widget for all Digifant 1 maps.

Each entry:
  'what'    — plain English description of what the map controls
  'tips'    — list of tuning tip strings
  'warning' — optional red warning string (dangerous edits)
"""

# ── Tip dictionary keyed by map name ─────────────────────────────────────────

MAP_TIPS: dict[str, dict] = {

    # ── 16×16 PRIMARY MAPS ────────────────────────────────────────────────────

    "Ignition": {
        "what": (
            "The primary ignition timing map. Each cell sets spark advance in °BTDC "
            "at a given RPM (columns) and engine load / MAP pressure (rows). "
            "The ECU reads this table millions of times per minute to decide exactly "
            "when to fire the spark plug."
        ),
        "tips": [
            "Rows are load (MAP pressure, kPa). Top rows = low load / cruise. "
            "Bottom rows = high load / WOT.",
            "Columns are RPM, left = low, right = high.",
            "More advance (higher °BTDC) = more power up to the knock threshold.",
            "Advance high-load cells cautiously — 1–2° at a time. Always monitor for knock.",
            "Stock tune is conservative. Tuned G60 chips typically add 5–12° at mid/high load.",
            "Cells decoded: °BTDC = (210 − raw) ÷ 2.86. Raw 90 ≈ 42°, raw 150 ≈ 21°.",
        ],
        "warning": (
            "Excessive advance under boost causes detonation. "
            "Detonation on a G60/G40 will destroy pistons quickly. "
            "Never advance high-load rows without a wideband AFR and knock monitoring."
        ),
    },

    "Ignition Map 1 (Low Load)": {
        "what": (
            "Triple-map variant: Map 1 is active at light throttle / low load. "
            "The ECU switches between all three ignition maps based on throttle position and load."
        ),
        "tips": [
            "This map covers cruise and light-throttle driving.",
            "Advance here improves fuel economy and throttle response.",
            "Safe to add 2–4° in mid-RPM cruise cells.",
        ],
        "warning": None,
    },

    "Ignition Map 2 (Mid Load)": {
        "what": (
            "Triple-map variant: Map 2 is the transition map, active between light throttle "
            "and WOT. Covers the mid-throttle driving range."
        ),
        "tips": [
            "This is where most street driving happens.",
            "Tune conservatively — knock is most likely in the mid-load transition zone.",
        ],
        "warning": "Monitor for knock carefully when advancing mid-load cells.",
    },

    "Ignition Map 3 (WOT)": {
        "what": (
            "Triple-map variant: Map 3 is active at WOT / full load. "
            "This is the most performance-critical ignition map."
        ),
        "tips": [
            "This map determines full-power ignition advance.",
            "Stock is very conservative — tuned cars typically add 8–12° here.",
            "Always pair WOT ignition changes with appropriate WOT fueling.",
        ],
        "warning": (
            "Advancing WOT cells on a boosted engine without proper fueling risks "
            "piston damage. Always tune fuel first, ignition second."
        ),
    },

    "Fuel": {
        "what": (
            "The primary fuel delivery map. Each cell sets injector pulse width "
            "(as a raw byte) at a given RPM and engine load. This is the most "
            "important map for air/fuel ratio control in the cruise and part-throttle range. "
            "Note: WOT fueling is handled separately by the WOT Enrichment tables."
        ),
        "tips": [
            "Higher raw value = more fuel (richer). Lower = less fuel (leaner).",
            "Rows are load (bottom = high load / near-WOT). Columns are RPM.",
            "Target λ1.0 (stoichiometric, ~14.7:1 AFR) for cruise cells.",
            "Richen high-load rows slightly for safety margin under boost.",
            "A wideband O2 sensor is essential for safe fuel map changes.",
            "The closed-loop lambda system will correct small errors at part throttle — "
            "WOT is open-loop, so accuracy matters most in the bottom rows.",
        ],
        "warning": (
            "Running lean under boost will cause detonation and piston damage. "
            "Always err richer rather than leaner in high-load cells."
        ),
    },

    # ── BOOST / ISV ───────────────────────────────────────────────────────────

    "RPM Scalar": {
        "what": (
            "16-entry RPM axis definition used by the boost cut and ISV tables. "
            "Each entry is a 16-bit value representing an RPM breakpoint. "
            "This defines the RPM scale that all boost/ISV maps reference."
        ),
        "tips": [
            "Do not edit unless you fully understand the RPM axis scaling.",
            "Changing these values shifts the RPM breakpoints for all boost-related maps.",
            "Stock values give even coverage from ~600 to 6300 RPM.",
        ],
        "warning": "Incorrect RPM scalar values will cause boost cut to trigger at wrong RPMs.",
    },

    "Boost Cut (No Knock)": {
        "what": (
            "MAP sensor pressure threshold (kPa) at which the ECU cuts boost "
            "when no knock is detected. One value per RPM breakpoint. "
            "If manifold pressure exceeds this value, fuel is cut to protect the engine."
        ),
        "tips": [
            "Higher values = boost cut triggers later = more boost allowed.",
            "Stock G60 cuts around 170–180 kPa (0.7–0.8 bar). Performance tunes raise this.",
            "Increase in small steps (5 kPa) and verify boost gauge readings.",
            "Values must be within the range of your MAP sensor (200 kPa stock, 250 kPa optional).",
        ],
        "warning": (
            "Raising the boost cut without supporting fueling and ignition changes "
            "risks engine damage. Boost cut is a safety net — respect it."
        ),
    },

    "Boost Cut (Knock)": {
        "what": (
            "MAP sensor pressure threshold (kPa) at which the ECU cuts boost "
            "when knock IS being detected. Always set lower than the no-knock table "
            "so the ECU protects the engine more aggressively under detonation."
        ),
        "tips": [
            "Should always be 10–20 kPa lower than the no-knock boost cut table.",
            "If the car is knocking at boost, this table determines the safety cutoff.",
            "Do not raise this table above the no-knock table.",
        ],
        "warning": (
            "This is an active safety mechanism. Setting it too high removes "
            "knock-based boost protection entirely."
        ),
    },

    "ISV Boost Control": {
        "what": (
            "Idle Stabilizer Valve (ISV) duty cycle vs RPM during boost events. "
            "The ISV is a solenoid bypass valve that routes air around the throttle plate. "
            "Under boost, the ECU uses this table to manage ISV opening to prevent "
            "boost spikes and stabilize transitions."
        ),
        "tips": [
            "Higher values = more ISV opening = more bypass air.",
            "Incorrect ISV control can cause boost spikes or poor throttle response.",
            "If disabling ISV via code patch, this table becomes irrelevant.",
            "The ISV is frequency and duty-cycle sensitive — even small changes affect idle quality.",
        ],
        "warning": None,
    },

    "Startup ISV vs ECT": {
        "what": (
            "ISV opening duty cycle vs engine coolant temperature at startup. "
            "Controls how much air bypasses the throttle to raise idle speed "
            "during cold start and warm-up."
        ),
        "tips": [
            "Left = cold engine, right = fully warm.",
            "Higher values = more air bypass = higher cold idle.",
            "If the car idles too high when cold, reduce values in the cold (left) end.",
            "If it stalls when cold, increase values.",
        ],
        "warning": None,
    },

    # ── WOT & ACCEL ───────────────────────────────────────────────────────────

    "WOT Enrichment": {
        "what": (
            "Sustained WOT fuel enrichment — the open-loop fuel level held for the entire "
            "time WOT is active. Once the ECU finally exits closed-loop after the Digi-Lag "
            "period, it settles onto this table (combined with the main fuel map) as its "
            "steady-state WOT fueling target. Think of it as the cruise control for WOT AFR."
        ),
        "tips": [
            "Higher values = richer sustained WOT mixture.",
            "This works in conjunction with the main fuel map — both contribute at WOT.",
            "Stock values are conservative. Performance tunes increase this for safer AFRs under boost.",
            "Target 11.5:1–12.5:1 AFR at WOT on a boosted G60/G40.",
            "Every gear change resets the Digi-Lag cycle — the ECU must reach this table "
            "again after each shift. This is why the car feels strong mid-gear but "
            "stumbles briefly after every gearchange at full throttle.",
        ],
        "warning": (
            "Lean WOT fueling on a supercharged engine causes detonation and piston damage. "
            "Always run richer than stoichiometric at WOT under boost."
        ),
    },

    "WOT Initial Enrichment": {
        "what": (
            "The immediate fuel shot fired the instant the WOT switch closes. "
            "This 9×5 table is your primary weapon against Digi-Lag.\n\n"
            "Digi-Lag is a deliberate VW firmware feature: at WOT the ECU does NOT "
            "immediately switch to open-loop. It stays in closed-loop lambda control for "
            "a preset time period (typically 1–3 seconds, RPM-dependent) while it "
            "compensates for the change in carbon canister scavenging pressure at WOT. "
            "During this window the mixture cycles lean, sometimes to 16:1 or worse "
            "under boost. This table injects extra fuel at the moment of WOT to blunt "
            "that lean spike while the lag period runs out.\n\n"
            "Critically: Digi-Lag is time-based, not boost-based. A smaller pulley "
            "builds boost faster but the lag window is the same length — meaning "
            "the lean spike hits harder at higher boost levels."
        ),
        "tips": [
            "Increasing values here enriches the WOT transition, reducing the lean spike "
            "during the lag window.",
            "The Digilag code patch (Code Patches tab) addresses the root cause by "
            "disabling the lambda holdoff timer — use both together for best results.",
            "The SNS no-lag solution goes further: it removes reliance on the WOT switch "
            "entirely and triggers open-loop enrichment via MAP pressure (boost level) instead.",
            "Removing the carbon canister does NOT fix Digi-Lag — it is hardcoded "
            "in the ECU firmware regardless of hardware.",
            "Tune this alongside WOT Enrichment for a smooth WOT entry.",
            "Digi-Lag resets every gear change. More aggressive enrichment here "
            "directly improves mid-gear-change throttle response.",
            "Cold engine (left columns) typically needs more initial enrichment than warm.",
        ],
        "warning": (
            "Too much initial enrichment causes a rich stumble on WOT entry. "
            "Tune in small increments with a wideband AFR gauge. "
            "On a small-pulley G60 at high boost, the lean spike during lag can reach "
            "16:1 AFR — this is a serious detonation risk."
        ),
    },

    "CO Adj vs MAP": {
        "what": (
            "CO (carbon monoxide / mixture) adjustment vs MAP pressure. "
            "This is effectively the ECU's equivalent of the CO potentiometer trimmer — "
            "a base fuel correction applied across the load range. "
            "It adjusts the overall mixture richness at different MAP readings."
        ),
        "tips": [
            "Think of this as a global fuel trim per load point.",
            "The physical CO pot on the ECU loom is a rough trim — this table is the fine control.",
            "Raising all values enriches the mixture globally.",
            "Use this to compensate for injector size changes or AFM swaps.",
            "Stock CO pot setting is 500Ω. This table works on top of that base.",
        ],
        "warning": None,
    },

    "Accel Enrich Min ΔMAP": {
        "what": (
            "Minimum MAP pressure change (delta) required to trigger acceleration enrichment. "
            "When the throttle opens quickly, MAP rises rapidly — if the rise exceeds "
            "this threshold, the ECU fires an extra fuel shot to prevent lean stumble."
        ),
        "tips": [
            "Lower values = enrichment triggers more easily (more sensitive).",
            "Higher values = enrichment only triggers on hard throttle inputs.",
            "If the car stumbles on light throttle tip-in, lower these values.",
            "If enrichment fires too eagerly causing rich stumble, raise values.",
        ],
        "warning": None,
    },

    "Accel Enrich Mult ECT": {
        "what": (
            "Acceleration enrichment multiplier vs engine coolant temperature. "
            "Scales the size of the fuel shot on throttle tip-in based on how warm "
            "the engine is. Cold engines need more enrichment to prevent stumble."
        ),
        "tips": [
            "Left = cold engine, right = fully warm.",
            "Higher multiplier = bigger fuel shot on acceleration.",
            "If the car stumbles when cold on tip-in, increase cold-end values.",
            "Warm-end values can usually be left close to stock.",
        ],
        "warning": None,
    },

    "Accel Enrich Adder ECT": {
        "what": (
            "Acceleration enrichment adder vs ECT — an additive (not multiplicative) "
            "fuel correction applied on top of the multiplier during throttle tip-in. "
            "Works together with the multiplier table to shape the total accel enrichment pulse."
        ),
        "tips": [
            "This adds a flat amount of fuel on top of the multiplier result.",
            "Tune the multiplier first, then use this for fine-tuning the shape.",
            "Cold-end values are more impactful for fixing cold stumble.",
        ],
        "warning": None,
    },

    # ── KNOCK & DWELL ─────────────────────────────────────────────────────────

    "Coil Dwell": {
        "what": (
            "Ignition coil dwell time vs RPM. Dwell is the time the coil primary "
            "circuit is energized before firing, measured in degrees of crankshaft rotation. "
            "Longer dwell = more energy stored in the coil = stronger spark."
        ),
        "tips": [
            "Stock values are calibrated for the OEM coil.",
            "If running a high-energy aftermarket coil, you may need to reduce dwell "
            "to prevent coil overheating.",
            "At high RPM, available dwell time decreases — stock table accounts for this.",
            "Do not increase dwell without confirming the coil can handle the heat.",
        ],
        "warning": "Excessive dwell overheats the coil and ignition driver transistor.",
    },

    "Knock Multiplier": {
        "what": (
            "Scaling factor applied to the knock sensor signal vs RPM. "
            "The ECU uses this to normalize the knock sensor's sensitivity "
            "across the RPM range, since engine noise (mechanical noise floor) "
            "increases with RPM."
        ),
        "tips": [
            "Higher values = more sensitive knock detection at that RPM.",
            "Stock values are calibrated for the stock engine.",
            "If getting false knock triggers at high RPM, reduce high-RPM values slightly.",
            "Do not reduce across the board — this disables knock protection.",
        ],
        "warning": "Reducing knock sensitivity removes engine protection against detonation.",
    },

    "Knock Retard Rate": {
        "what": (
            "How quickly the ECU retards ignition timing (degrees per event) "
            "when knock is detected. Higher values = timing pulled back faster "
            "in response to detected knock."
        ),
        "tips": [
            "Stock is calibrated to react quickly enough to prevent damage.",
            "Increasing this gives more aggressive knock protection but may cause "
            "noticeable power dips during knock events.",
            "Leave close to stock unless you have a specific reason to change it.",
        ],
        "warning": None,
    },

    "Knock Decay Rate": {
        "what": (
            "How quickly the ECU recovers timing advance after a knock event ends. "
            "Once knock stops, the ECU slowly restores timing — this table controls "
            "how fast that recovery happens."
        ),
        "tips": [
            "Higher values = faster recovery back to full advance after knock clears.",
            "Too fast recovery can allow knock to re-occur before conditions change.",
            "Leave close to stock for road use.",
        ],
        "warning": None,
    },

    # ── IDLE & IGNITION ───────────────────────────────────────────────────────

    "Advance vs ECT": {
        "what": (
            "Ignition timing advance correction vs engine coolant temperature. "
            "Applied on top of the main ignition map during warm-up. "
            "Cold engines typically need slightly more advance; "
            "very cold starts may need slightly less."
        ),
        "tips": [
            "Left = cold engine, right = fully warm.",
            "This is a small additive correction to the main ignition map.",
            "If timing seems off during warm-up, adjust the cold-end values.",
        ],
        "warning": None,
    },

    "Idle Advance Time": {
        "what": (
            "Ignition timing used during idle stabilization. The ISC (Idle Speed Control) "
            "system uses ignition timing as a fast-acting tool to hold idle speed — "
            "advancing timing increases idle RPM slightly, retarding it decreases RPM."
        ),
        "tips": [
            "This controls how aggressively timing moves to stabilize idle.",
            "If idle hunts or is unstable, check ISV condition before editing this.",
            "Changes here interact with the ISV — both must be in good condition.",
        ],
        "warning": None,
    },

    "Idle Ign High Limit": {
        "what": (
            "Maximum ignition advance allowed during idle stabilization. "
            "The ECU will not advance past this table's values when using "
            "timing-based idle control, preventing over-advance at idle."
        ),
        "tips": [
            "Acts as a ceiling for the idle stabilization timing range.",
            "Raising these values allows more advance authority at idle.",
            "If idle RPM can't reach target, ensure this isn't clamping the advance.",
        ],
        "warning": None,
    },

    "Idle Ign Low Limit": {
        "what": (
            "Minimum ignition advance allowed during idle stabilization. "
            "The ECU will not retard below this when using timing-based idle control. "
            "Prevents excessive retard that would cause rough idle or stalling."
        ),
        "tips": [
            "Acts as a floor for the idle stabilization timing range.",
            "If idle is lumpy or the car stalls on deceleration, check this table.",
            "Lowering values gives more retard authority but risks rough idle.",
        ],
        "warning": None,
    },

    "Idle Ignition": {
        "what": (
            "Base ignition timing target at idle vs RPM. This is the starting point "
            "for the idle stabilization system before corrections are applied. "
            "Sets the nominal idle timing the ECU aims for."
        ),
        "tips": [
            "This is the 'resting' timing value at idle.",
            "Physical base timing (distributor) should be set to spec first.",
            "Changes here shift the entire idle timing baseline up or down.",
        ],
        "warning": None,
    },

    # ── TEMPERATURE ───────────────────────────────────────────────────────────

    "Warm Up Enrichment": {
        "what": (
            "Fuel enrichment multiplier vs engine coolant temperature during warm-up. "
            "Cold engines need a richer mixture to atomize fuel properly and run smoothly "
            "before the catalytic converter and O2 sensor reach operating temperature."
        ),
        "tips": [
            "Left = cold engine, right = fully warm.",
            "Higher values = richer mixture during warm-up.",
            "If the car runs rough when cold, try increasing cold-end values.",
            "If it runs rich and sooty when cold, reduce cold-end values.",
            "Right end should taper to 0 (no enrichment) when fully warm.",
        ],
        "warning": None,
    },

    "IAT Compensation": {
        "what": (
            "Fuel correction vs intake air temperature (IAT). "
            "Hot air is less dense than cold air — this table richens the mixture "
            "as IAT increases to compensate for the reduced air mass. "
            "Prevents lean conditions on hot days or after heat-soaked supercharger runs."
        ),
        "tips": [
            "Left = cold intake air, right = hot intake air.",
            "Higher values = more fuel added for hot air.",
            "On a supercharged car with a hot intercooler or no intercooler, "
            "the right end of this table is critical.",
            "If AFRs lean out on hot days, increase high-temp values.",
        ],
        "warning": None,
    },

    "ECT Compensation 1": {
        "what": (
            "First fuel correction table vs engine coolant temperature. "
            "Applies a fuel trim based on engine temp across the full operating range. "
            "Works alongside ECT Compensation 2 for fine-grained cold/warm fuel control."
        ),
        "tips": [
            "Left = cold, right = warm.",
            "Both ECT comp tables work together — change one then check the other.",
            "Use for fine-tuning fueling across the warm-up curve.",
        ],
        "warning": None,
    },

    "ECT Compensation 2": {
        "what": (
            "Second fuel correction table vs engine coolant temperature. "
            "Works in combination with ECT Compensation 1 to provide full warm-up "
            "fuel control. The two tables are additive."
        ),
        "tips": [
            "Left = cold, right = warm.",
            "Tune ECT Comp 1 first for the general shape, use this for fine detail.",
        ],
        "warning": None,
    },

    "Startup Enrichment": {
        "what": (
            "Extra fuel pulse added immediately at crank/start vs ECT. "
            "Provides the initial fuel shot when the engine is cranking to aid starting. "
            "Higher values = larger startup shot = easier cold starting."
        ),
        "tips": [
            "Left = cold, right = warm.",
            "If the car cranks but takes a long time to fire when cold, increase cold-end.",
            "If it starts rich and loads up (black smoke, fouled plugs), reduce cold-end.",
            "Hot start enrichment is handled by a separate table.",
        ],
        "warning": None,
    },

    "Hot Start Enrichment": {
        "what": (
            "Extra fuel enrichment for restarting a hot engine (heat soak start). "
            "When a hot engine is restarted, fuel can vaporize in the intake causing "
            "a lean condition. This table adds fuel to compensate."
        ),
        "tips": [
            "If the car is hard to restart when hot (after a short stop), increase these values.",
            "If it starts rich and stumbles when hot, reduce values.",
            "Heat-soak starts are a common Digifant complaint — this table addresses it directly.",
        ],
        "warning": None,
    },

    "Battery Compensation": {
        "what": (
            "Injector pulse width correction vs battery voltage. "
            "At low voltage, injectors open more slowly, effectively delivering less fuel. "
            "This table adds extra pulse width to compensate for voltage-dependent injector lag."
        ),
        "tips": [
            "Left = low voltage (weak battery / cranking), right = high voltage (charging).",
            "Higher values = more added pulse width at low voltage.",
            "If the car runs lean immediately after start (when voltage is low), "
            "check/increase low-voltage values.",
            "Important if running an upgraded alternator or high-drain accessories.",
        ],
        "warning": None,
    },

    # ── LAMBDA / OXS ─────────────────────────────────────────────────────────

    "Injector Lag": {
        "what": (
            "Injector opening delay (dead time) compensation vs battery voltage. "
            "Injectors take a finite time to open after being triggered — this varies "
            "with voltage. The ECU adds extra time to the commanded pulse to compensate, "
            "ensuring the actual fuel delivery matches the commanded amount."
        ),
        "tips": [
            "Left = low voltage (larger lag compensation needed), right = high voltage.",
            "This is calibrated for the stock injectors. If fitting larger injectors, "
            "you must re-calibrate this table for the new injectors' dead time.",
            "Wrong injector lag causes fuel delivery errors at idle and light throttle "
            "where pulse widths are short.",
            "Injector dead time specs are available from injector manufacturers.",
        ],
        "warning": (
            "Incorrect injector lag causes poor idle and fueling errors at light load. "
            "Always update this table when changing injectors."
        ),
    },

    "OXS Upswing": {
        "what": (
            "Oxygen sensor (lambda) correction upswing table — controls how much "
            "the ECU richens the mixture per correction step during closed-loop lambda control. "
            "This is a 16×4 table (RPM × load zones). "
            "When the O2 sensor reads lean, the ECU applies this correction to add fuel."
        ),
        "tips": [
            "Higher values = larger richen correction step per lambda cycle.",
            "Larger values cause faster closed-loop response but can cause hunting (oscillation).",
            "Stock values give stable, smooth lambda correction.",
            "If the AFR oscillates widely at cruise, reduce these values.",
            "The SNS open-loop patch (Code Patches) bypasses this table entirely.",
        ],
        "warning": None,
    },

    "OXS Downswing": {
        "what": (
            "Oxygen sensor (lambda) correction downswing table — controls how much "
            "the ECU leans the mixture per correction step during closed-loop lambda control. "
            "This is a 16×4 table (RPM × load zones). "
            "When the O2 sensor reads rich, the ECU applies this correction to remove fuel."
        ),
        "tips": [
            "Higher values = larger lean correction step per lambda cycle.",
            "Should be balanced with the OXS Upswing table.",
            "Asymmetric upswing/downswing values cause the lambda to oscillate around "
            "a biased point (useful for running slightly rich at cruise).",
            "The SNS open-loop patch (Code Patches) bypasses this table entirely.",
        ],
        "warning": None,
    },
}

# Fallback tip for unknown maps
_UNKNOWN_TIP = {
    "what": "No description available for this map yet.",
    "tips": ["Proceed with caution. Observe changes carefully on a running engine."],
    "warning": None,
}


def get_tip(map_name: str) -> dict:
    """Return the tip dict for a given map name, falling back to generic."""
    return MAP_TIPS.get(map_name, _UNKNOWN_TIP)


# ── TipPanel widget ───────────────────────────────────────────────────────────

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QScrollArea, QSizePolicy
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class TipPanel(QWidget):
    """
    Right-side panel showing map description, tuning tips, and optional warning.
    Call show_tip(map_name) to update the content.
    Fixed width ~260px — sits alongside the map/table content.
    """

    PANEL_WIDTH = 260

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(self.PANEL_WIDTH)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setStyleSheet("background: #0d1117;")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: #0d1117; border: none;")
        root.addWidget(scroll)

        self._content = QWidget()
        self._content.setStyleSheet("background: #0d1117;")
        self._col = QVBoxLayout(self._content)
        self._col.setContentsMargins(12, 12, 12, 12)
        self._col.setSpacing(10)
        scroll.setWidget(self._content)

        # Map name header
        self._lbl_name = QLabel("")
        self._lbl_name.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self._lbl_name.setStyleSheet("color: #00d4ff;")
        self._lbl_name.setWordWrap(True)
        self._col.addWidget(self._lbl_name)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("color: #1a2332;")
        self._col.addWidget(div)

        # "What it does" section
        self._lbl_what_hdr = QLabel("What it does")
        self._lbl_what_hdr.setStyleSheet(
            "color: #7ab3cc; font-size: 10px; font-weight: bold; text-transform: uppercase;"
            "letter-spacing: 1px; margin-top: 4px;"
        )
        self._col.addWidget(self._lbl_what_hdr)

        self._lbl_what = QLabel("")
        self._lbl_what.setWordWrap(True)
        self._lbl_what.setStyleSheet("color: #bccdd8; font-size: 11px; line-height: 1.4;")
        self._lbl_what.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._col.addWidget(self._lbl_what)

        # Divider
        div2 = QFrame()
        div2.setFrameShape(QFrame.HLine)
        div2.setStyleSheet("color: #1a2332;")
        self._col.addWidget(div2)

        # Tuning tips section
        self._lbl_tips_hdr = QLabel("Tuning tips")
        self._lbl_tips_hdr.setStyleSheet(
            "color: #7ab3cc; font-size: 10px; font-weight: bold; text-transform: uppercase;"
            "letter-spacing: 1px; margin-top: 4px;"
        )
        self._col.addWidget(self._lbl_tips_hdr)

        self._tips_container = QWidget()
        self._tips_container.setStyleSheet("background: #0d1117;")
        self._tips_layout = QVBoxLayout(self._tips_container)
        self._tips_layout.setContentsMargins(0, 0, 0, 0)
        self._tips_layout.setSpacing(6)
        self._col.addWidget(self._tips_container)

        # Warning box (hidden when no warning)
        self._warn_box = QWidget()
        self._warn_box.setStyleSheet(
            "background: #1a0a00; border: 1px solid #7a3000; border-radius: 4px;"
        )
        warn_layout = QVBoxLayout(self._warn_box)
        warn_layout.setContentsMargins(8, 6, 8, 6)

        self._lbl_warn_hdr = QLabel("⚠  Warning")
        self._lbl_warn_hdr.setStyleSheet(
            "color: #e8793a; font-size: 10px; font-weight: bold;"
        )
        warn_layout.addWidget(self._lbl_warn_hdr)

        self._lbl_warn = QLabel("")
        self._lbl_warn.setWordWrap(True)
        self._lbl_warn.setStyleSheet("color: #e8b84b; font-size: 11px; line-height: 1.4;")
        self._lbl_warn.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        warn_layout.addWidget(self._lbl_warn)

        self._col.addWidget(self._warn_box)
        self._col.addStretch()

        self.show_tip("")  # start blank

    def show_tip(self, map_name: str):
        tip = get_tip(map_name) if map_name else _UNKNOWN_TIP

        self._lbl_name.setText(map_name or "—")
        self._lbl_what.setText(tip.get("what", ""))

        # Rebuild tips
        while self._tips_layout.count():
            item = self._tips_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for t in tip.get("tips", []):
            row = QWidget()
            row.setStyleSheet("background: #0d1117;")
            rl = QVBoxLayout(row)  # Use VBox so long tips wrap properly
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(0)

            # Bullet + text in a horizontal layout
            hl = QWidget()
            hl.setStyleSheet("background: #0d1117;")
            hll = QVBoxLayout(hl)
            hll.setContentsMargins(0, 0, 0, 0)

            lbl = QLabel(f"• {t}")
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: #8aa8bb; font-size: 11px; line-height: 1.4;")
            lbl.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            hll.addWidget(lbl)
            rl.addWidget(hl)
            self._tips_layout.addWidget(row)

        # Warning
        warning = tip.get("warning")
        if warning:
            self._lbl_warn.setText(warning)
            self._warn_box.setVisible(True)
        else:
            self._warn_box.setVisible(False)

# Credits & Acknowledgements

DigiTool stands on the shoulders of years of community reverse engineering work.
These are the people and projects that made it possible.

---

## Yousaf Nabi — YOU54F

**GitHub:** https://github.com/YOU54F
**Project:** [PoloG40Digifant](https://github.com/YOU54F/PoloG40Digifant)
**Wiki:** https://github.com/YOU54F/PoloG40Digifant/wiki

The most comprehensive public decompilation of the Digifant 1 controller available.
Yousaf's binary decompilation work with IDA Pro, map table documentation, code
modification guides, and collection of stock G40 EPROMs form the primary technical
foundation for DigiTool's map offsets, code patch detection, and ROM fingerprinting.

Specific contributions referenced:
- G40 / G60 map table locations and addresses (ignition, fuel, RPM scalar, boost cut, ISV, WOT enrichment, corrections)
- RPM limiter and RPM scalar formulas (`30,000,000 / value`, `15,000,000 / value`)
- Ignition formula: `(210 - value) / 2.86 = °BTDC`
- Load axis explanation: 200kPa sensor → 16 equal slices. 250kPa sensor swap requires rescaling all boost-indexed maps
- G60 custom code analysis: digilag, open-loop lambda, ISV disable patch addresses
- Triple-map ISV boost control documentation (`x481C`, `x482D`, `x483E`)
- G40 code modification documentation
- Stock G40 EPROM files (`G40_StockEprom.BIN`, `G40_Mk2_StockEprom.BIN`)

---

## Dominik Gummel

**Site:** http://gummel.net/bofh-ng/en/digifant-1-en/digifant-1-read-live-data-over-serial-k-line

Live data logging over K-line for Digifant 1, including an Android app and PC/Linux
versions. Shows map values, knock flags, and live sensor data. Invaluable reference
for understanding what the ECU is actually doing at runtime.

---

## designer2k2

**GitHub:** https://github.com/designer2k2/multidisplay

Open-source K-line logger supporting Digifant 1 with Dominik Gummel's modified ECU
code. Good reference for the serial protocol implementation.

---

## Rafal M. — DigifantTool (original)

**Facebook:** https://m.facebook.com/tuningtool/

Built a Bluetooth EPROM emulator for Digifant 1 and modified ECU code to output live
values to TunerPro via an ADX file. Note: this project shares a similar name with
DigifantTool (this repo) but is a separate, independent tool focused on live data
and emulation rather than ROM editing.

---

## KDA

Russian developer who wrote their own Digifant 1 logging protocol and software with
extensive feature support. See the PoloG40Digifant wiki KDA logging section for details.

---

## Club G40

**Site:** https://www.polog40.co.uk

Long-running UK Polo G40 owners club. Technical articles on the Digifant 1 ECU
hardware, MAP sensor operation, chipping guides, and ECU pinouts were useful
cross-references during development.

---

## Notes

- VW/Bosch factory firmware is copyright Bosch GmbH / Volkswagen AG.
- Stock ROM files in `roms/` are provided for educational and restoration purposes,
  consistent with long-standing Digifant community practice.
- DigiTool (this repo) is an independent open-source project with no affiliation
  to Volkswagen AG, Bosch GmbH, or any tuner / tool listed above.

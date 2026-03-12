# Credits & Acknowledgements

DigifantTool stands on the shoulders of years of community reverse engineering work.
These are the people and projects that made it possible.

---

## Yousaf Nabi — YOU54F

**Project:** [PoloG40Digifant](https://github.com/YOU54F/PoloG40Digifant)
**Wiki:** https://github.com/YOU54F/PoloG40Digifant/wiki

The most comprehensive public decompilation of the Digifant 1 controller available.
Yousaf's binary decompilation work with IDA Pro, map table documentation, code
modification guides, and collection of stock G40 EPROMs form the primary technical
foundation for DigifantTool's map offsets, code patch detection, and ROM fingerprinting.

Specific contributions referenced:
- G40 / G60 map table locations and addresses
- RPM limiter, RPM scalar, ignition and fuel map layout
- G60 custom code analysis (digilag, open-loop lambda, ISV disable patch addresses)
- G40 code modification documentation
- Stock G40 EPROM files (`G40_StockEprom.BIN`, `G40_Mk2_StockEprom.BIN`)

---

## Club G40

**Site:** https://www.polog40.co.uk

Long-running UK Polo G40 owners club. Technical articles on the Digifant 1 ECU
hardware, MAP sensor operation, chipping guides, and ECU pinouts were useful
cross-references during development.

---

## VW Vortex — Digifant Community

**Thread:** Digifant Microcontroller and EEPROM
https://www.vwvortex.com/threads/digifant-microcontroller-and-eeprom.2593573/

Early community documentation of the MC68HC11 processor, EPROM type, and
Digifant tuning approaches. Useful background on the G60 system architecture.

---

## SNS Tuning / BBM Motorsport / TT Chip

Aftermarket tuners whose publicly discussed work helped the community understand
what was tuneable in the Digifant 1 ROM and how the maps behave under modification.
Not directly affiliated with DigifantTool.

---

## Notes

- VW/Bosch factory firmware is copyright Bosch GmbH / Volkswagen AG.
- Stock ROM files in `roms/` are provided for educational and restoration purposes,
  consistent with long-standing Digifant community practice.
- DigifantTool itself is an independent open-source project with no affiliation
  to Volkswagen AG, Bosch GmbH, or any aftermarket tuner.

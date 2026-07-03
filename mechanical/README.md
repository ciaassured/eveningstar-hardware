# EveningStar slot-fit case

This directory contains a generated two-piece enclosure for
`pcb/EveningStar.kicad_pcb`.

The PCB is not screwed into the case. It sits in a close-fitting internal tray
with long edge rails, and the lid screws land in external ears outside the case
body.

Generated files:

- `eveningstar_case_slotfit_base.step` / `eveningstar_case_slotfit_base.stl`:
  main body with edge support rails and external insert ears
- `eveningstar_case_slotfit_lid.step` / `eveningstar_case_slotfit_lid.stl`:
  flat lid with matching external screw ears
- `eveningstar_case_slotfit.FCStd`: FreeCAD document with base, lid, and PCB
  reference
- `eveningstar_case_slotfit_pcb_reference.step`: PCB outline reference
- `eveningstar_case_slotfit_report.json`: extracted dimensions and hole
  positions

Regenerate with:

```sh
bash scripts/generate_eveningstar_case.sh
```

Hardware assumptions:

- Four M2.5 heat-set threaded inserts in the external ears
- Insert pilot holes: 3.6 mm diameter x 6.0 mm deep
- Lid screw clearance holes: 3.0 mm diameter
- Two M3 clearance holes through the case bottom for the DIN rail bracket
  model in this directory. The holes are centered on the case body and use the
  bracket's 52.5 mm insert pitch.

Fit assumptions:

- PCB edge clearance is 0.55 mm per side.
- Long solid ribs support the PCB and run down to the inside floor, avoiding
  unsupported rail overhangs during printing.
- Board bottom sits 4.8 mm above the bottom outside face.
- The board is 2.8 mm above the inside floor, leaving about 0.5 mm clearance
  for the deepest bottom-side geometry found in the current KiCad 3D export.
- The USB-C side opening is a raised slot above the rail height, not a full
  side-wall hole down to the floor.

The lid includes tool-access holes for `S1`/`CFG_SW`, `S2`/`RST_SW`, and
`S3`/`BOOT_SW`, plus viewing holes for `D4`/`TX`, `D6`/`RX`, and `D12`/`White`.
Side openings are generated for the RJ11 MeterBus jack, RJ45 Ethernet jack,
barrel jack, and USB-C connector.

The dimensions and clearances are configured near the top of
`scripts/generate_eveningstar_case.py` in `CaseConfig`.

# EveningStar slot-fit cases

This directory contains generated two-piece enclosures for
`pcb/EveningStar.kicad_pcb`.

The PCB is not screwed into the case. It sits in a close-fitting internal tray
with long edge rails. There are four generated variants:

- `slotfit`: lid screws land in external ears outside the case body.
- `snapfit`: no lid screws; four tapered nubs on the long case walls snap into
  matching recesses in a lid shoulder.
- `lowprofile`: screwless snap-fit body with shorter walls and top lid
  pass-throughs for tall components.
- `skeletonized`: low-profile snap-fit body with through-cut rib slots in the
  bottom floor and lid plate to reduce filament while keeping the functional
  snap, rail, DIN mount, connector, switch, LED, and sensor clearances.

Generated files:

- `eveningstar_case_slotfit_base.step` / `eveningstar_case_slotfit_base.stl`:
  main body with edge support rails and external insert ears
- `eveningstar_case_slotfit_lid.step` / `eveningstar_case_slotfit_lid.stl`:
  flat lid with matching external screw ears
- `eveningstar_case_slotfit.FCStd`: FreeCAD document with base, lid, and PCB
  reference
- `eveningstar_case_slotfit_pcb_reference.step`: PCB outline reference with
  raised connector markers on the component side
- `eveningstar_case_slotfit_report.json`: extracted dimensions and hole
  positions
- `eveningstar_case_snapfit_base.step` / `eveningstar_case_snapfit_base.stl`:
  screwless body with the same PCB tray, DIN rail holes, connector openings,
  and snap nubs
- `eveningstar_case_snapfit_lid.step` / `eveningstar_case_snapfit_lid.stl`:
  lid with an internal shoulder and matching snap recesses
- `eveningstar_case_snapfit.FCStd`: FreeCAD document with snapfit base, lid,
  and PCB reference
- `eveningstar_case_snapfit_pcb_reference.step`: PCB outline reference with
  raised connector markers on the component side
- `eveningstar_case_snapfit_report.json`: extracted dimensions and snap
  positions
- `eveningstar_case_lowprofile_base.step` /
  `eveningstar_case_lowprofile_base.stl`: shorter snap-fit body that stops
  close to the PCB top instead of enclosing the tallest parts
- `eveningstar_case_lowprofile_lid.step` /
  `eveningstar_case_lowprofile_lid.stl`: lid with pass-through cutouts for the
  programming header, 3V3 power jumper, MeterBus jack, Ethernet jack, barrel
  jack, and AHT20 air opening
- `eveningstar_case_lowprofile.FCStd`: FreeCAD document with low-profile base,
  lid, and PCB reference
- `eveningstar_case_lowprofile_pcb_reference.step`: PCB outline reference with
  raised connector markers on the component side
- `eveningstar_case_lowprofile_report.json`: extracted low-profile dimensions,
  pass-through openings, and AHT20 vent details
- `eveningstar_case_skeletonized_base.step` /
  `eveningstar_case_skeletonized_base.stl`: low-profile snap-fit body with an
  open ribbed floor and solid DIN screw pads
- `eveningstar_case_skeletonized_lid.step` /
  `eveningstar_case_skeletonized_lid.stl`: low-profile lid with support-free
  through-cut rib slots around the existing control, LED, component, and sensor
  openings
- `eveningstar_case_skeletonized.FCStd`: FreeCAD document with skeletonized
  base, lid, and PCB reference
- `eveningstar_case_skeletonized_pcb_reference.step`: PCB outline reference
  with raised connector markers on the component side
- `eveningstar_case_skeletonized_report.json`: extracted dimensions, slot
  counts, preserved keepouts, and modeled volume reduction versus `lowprofile`

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
- Snapfit lid shoulder clearance is 0.25 mm per side.
- Snapfit nubs are 20.0 mm wide x 2.0 mm high with a 1.0 mm triangular
  protrusion. They are placed in pairs on the front and back walls to avoid the
  side connector openings.

Fit assumptions:

- PCB edge clearance is 0.55 mm per side.
- Long solid ribs support the PCB and run down to the inside floor, avoiding
  unsupported rail overhangs during printing.
- Board bottom sits 4.8 mm above the bottom outside face.
- The board is 2.8 mm above the inside floor, leaving about 0.5 mm clearance
  for the deepest bottom-side geometry found in the current KiCad 3D export.
- The USB-C side opening is a raised slot above the rail height, not a full
  side-wall hole down to the floor.
- PCB-derived features use the KiCad 3D export orientation, so component-side
  connector markers in the PCB reference line up with the case side openings.
- The low-profile variant uses a 10.6 mm base height. With the current tray
  dimensions, the PCB top is at 6.4 mm, leaving 4.2 mm over the board for
  smaller components while taller connectors protrude through the lid.
- The low-profile AHT20 opening combines an 8.0 mm top aperture with a front
  side window because `U6` sits near the front PCB edge.
- The skeletonized variant keeps the same low-profile snap-fit envelope and
  uses rounded through-slots only in surfaces that face the print bed: 22 floor
  slots and 12 lid slots in the current generated files. The report estimates a
  23.8% modeled solid-volume reduction versus `lowprofile`.

The lid includes tool-access holes for `S1`/`CFG_SW`, `S2`/`RST_SW`, and
`S3`/`BOOT_SW`, plus viewing holes for `D4`/`TX`, `D6`/`RX`, and `D12`/`White`.
Side openings are generated for the RJ11 MeterBus jack, RJ45 Ethernet jack,
barrel jack, and USB-C connector.

The snapfit variant follows the tapered triangular nub plus lid-shoulder
recess pattern used by the BoxMaker Fusion snap-fit enclosure generator, with
clearance values in the same range as the downloaded snap-fit case references.

The dimensions and clearances are configured near the top of
`scripts/generate_eveningstar_case.py` in `CaseConfig`.

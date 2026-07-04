# EveningStar slot-fit cases

This directory contains generated two-piece enclosures for
`pcb/EveningStar.kicad_pcb`.

The PCB is not screwed into the case. It sits in a close-fitting internal tray
with long edge rails. There are five generated variants:

- `slotfit`: lid screws land in external ears outside the case body.
- `snapfit`: no lid screws; four tapered nubs on the long case walls snap into
  matching recesses in a lid shoulder.
- `lowprofile`: screwless snap-fit body with shorter walls and top lid
  pass-throughs for tall components.
- `lowprofile_din_slide`: low-profile body with a side-mounted dovetail rail
  on the no-I/O side and a screwless slide-on original-style DIN rail clip.
- `skeletonized`: low-profile snap-fit body with faceted hex-ended lattice
  cells in the bottom floor and lid plate to reduce filament while keeping the
  functional snap, rail, DIN mount, connector, switch, LED, and sensor
  clearances.

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
- `eveningstar_case_lowprofile_din_slide_base.step` /
  `eveningstar_case_lowprofile_din_slide_base.stl`: low-profile body variant
  with the old M3 DIN screw holes omitted and a side dovetail rail on the
  max-Y wall opposite the USB-C connector
- `eveningstar_case_lowprofile_din_slide_lid.step` /
  `eveningstar_case_lowprofile_din_slide_lid.stl`: the matching low-profile
  lid export for the side-slide variant
- `eveningstar_case_lowprofile_din_slide.FCStd`: FreeCAD document with the
  side-rail base, lid, PCB reference, and original-style side DIN clip placed
  in its installed position
- `eveningstar_case_lowprofile_din_slide_pcb_reference.step`: PCB outline
  reference with raised connector markers on the component side
- `eveningstar_case_lowprofile_din_slide_report.json`: extracted dimensions
  for the side rail, receiver clearance, insertion direction, and installed
  clip envelope
- `din-rail-side-clip-original-lowprofile.step` /
  `din-rail-side-clip-original-lowprofile.stl`: print-oriented side-slide
  clip using the original `din-rail-bracket-heat-insert-version.step` DIN mount
  with an integrated side-slide receiver
- `eveningstar_case_skeletonized_base.step` /
  `eveningstar_case_skeletonized_base.stl`: low-profile snap-fit body with an
  open faceted lattice floor and solid DIN screw pads
- `eveningstar_case_skeletonized_lid.step` /
  `eveningstar_case_skeletonized_lid.stl`: low-profile lid with support-free
  through-cut faceted lattice cells around the existing control, LED,
  component, and sensor openings
- `eveningstar_case_skeletonized.FCStd`: FreeCAD document with skeletonized
  base, lid, and PCB reference
- `eveningstar_case_skeletonized_pcb_reference.step`: PCB outline reference
  with raised connector markers on the component side
- `eveningstar_case_skeletonized_report.json`: extracted dimensions, lattice
  cell counts, preserved keepouts, and modeled volume reduction versus
  `lowprofile`

Regenerate with:

```sh
bash scripts/generate_eveningstar_case.sh
```

Hardware assumptions:

- Four M2.5 heat-set threaded inserts in the external ears
- Insert pilot holes: 3.6 mm diameter x 6.0 mm deep
- Lid screw clearance holes: 3.0 mm diameter
- The original slotfit, snapfit, lowprofile, and skeletonized variants use two
  M3 clearance holes through the case bottom for the DIN rail bracket model in
  this directory. The holes are centered on the case body and use the bracket's
  52.5 mm insert pitch.
- The `lowprofile_din_slide` variant omits those M3 holes and instead uses a
  side-mounted dovetail rail on the max-Y wall. The side DIN clip slides on
  along the case X axis and is captured in Y/Z by the dovetail.
- Snapfit lid shoulder clearance is 0.25 mm per side.
- Snapfit-derived lid shoulders are locally relieved over the USB-C side
  opening so the alignment bar does not cross the port mouth.
- Snapfit nubs are 20.0 mm wide x 2.0 mm high with a 1.0 mm triangular
  protrusion. They are placed in pairs on the front and back walls to avoid the
  side connector openings.
- Base and lid mating perimeters are kept square so the lid sits flush on the
  top rim of the box. Fillets are limited to non-mating comfort edges.

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
- Snapfit-derived lid exports keep the internal shoulder facing up for
  support-free printing. PCB-derived lid openings are pre-mirrored in Y so they
  line up after the lid is turned over onto the base.
- The low-profile variant uses a 10.6 mm base height. With the current tray
  dimensions, the PCB top is at 6.4 mm, leaving 4.2 mm over the board for
  smaller components while taller connectors protrude through the lid.
- The low-profile AHT20 opening combines an 8.0 mm top aperture with a front
  side window because `U6` sits near the front PCB edge.
- The side DIN rail interface uses one external rounded dovetail-like rail on
  the max-Y wall from x=18.0 mm to x=133.4 mm. The rail protrudes 2.0 mm,
  starts at the print-bed plane on the case side and ramps outward to the lower
  capture at z=3.1 mm, making the attachment read more like an outward
  skateboard-ramp fairing than an inward fillet. The rail rises to 9.5 mm above
  the box bottom and has a 45 degree sloped upper face. The rail profile
  includes a 1.4 mm high root that overlaps the original bottom-side box fillet
  so the rail grows out of the case corner more uniformly. Exposed non-bed rail
  edges use a 0.25 mm fillet, while rail/root edges that contact the main box
  are left unfilleted. The clip receiver uses 0.3 mm nominal clearance and is
  exported with the receiver opening on the print bed. Its
  visible upper and lower capture faces match the box rail angles, then the
  receiver back chamfers into a 1.4 mm deep internal point instead of a flat
  bridge surface. The box has no bottom slot or hidden bridge. The obsolete
  screw-hole plugs in the original DIN clip use sharp-edged flat caps that
  cover the old hole bevel by 0.02 mm per face and add 0.85 mm radial cover
  over the former hole diameter, hiding the original filleted rim without the
  previous tall fill bosses.
- The skeletonized variant keeps the same low-profile snap-fit envelope and
  uses faceted hex-ended through-cells only in surfaces that face the print bed:
  22 floor lattice cells and 12 lid lattice cells in the current generated
  files. The report estimates a 21.1% modeled solid-volume reduction versus
  `lowprofile`.

The lid includes tool-access holes for `S1`/`CFG_SW`, `S2`/`RST_SW`, and
`S3`/`BOOT_SW`, plus viewing holes for `D4`/`TX`, `D6`/`RX`, and `D12`/`White`.
Side openings are generated for the RJ11 MeterBus jack, RJ45 Ethernet jack,
barrel jack, and USB-C connector.

The snapfit variant follows the tapered triangular nub plus lid-shoulder
recess pattern used by the BoxMaker Fusion snap-fit enclosure generator, with
clearance values in the same range as the downloaded snap-fit case references.

The dimensions and clearances are configured near the top of
`scripts/generate_eveningstar_case.py` in `CaseConfig`.

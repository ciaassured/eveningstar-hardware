# EasyEDA library

Symbols, footprints, and 3D models pulled in via `easyeda2kicad.py`.

## 3D models: use `.step`, and keep the offsets

Every model in `EasyEDA.3dshapes` ships as both `.wrl` and `.step`. The
footprints and the board reference the **`.step`** files.

The `.wrl` files are unusable: KiCad's VRML parser rejects them outright
(`readVRML() failed ... No model for filename ...`), so any footprint pointing
at one renders as empty space. They are also skipped by `kicad-cli pcb export
step` and every other non-mesh export. They are kept only as the reference for
correct part placement — see below.

The two formats do **not** share a datum. `easyeda2kicad.py` writes the `.wrl`
with z = 0 at the seating plane, but writes the `.step` with its own origin,
often at the body centre and occasionally somewhere unrelated. The geometry is
identical — measured heights agree to 0.001 mm — only the origin moves. So each
`(model ...)` needs an `(offset ...)` that puts the `.step` back where the
`.wrl` had it. The values currently in use:

| Model | offset (xyz) |
| --- | --- |
| `SMB_L4.6-W3.6-LS5.3-BI` | `0 0 0.1` |
| `SMB_L4.3-W3.6-LS5.4-BI` | `0 0 1.535` |
| `FUSE-SMD_L6.1-W2.6-H2.6` | `0 0 1.3` |
| `L0603_L1.6-W0.8-H0.5_BEAD` | `0 0 0.25` |
| `WSON-8_L8.0-W6.0-P1.27-TL-1` | `0 0 0.02` |
| `ESOP-8_L4.9-W3.9-P1.27-LS6.0-BL-EP-1` | `0 0 0.8` |
| `SOP-8_L4.9-W3.9-P1.27-LS6.0-BL_ISO6721RBDR` | `0 0 0.95` |
| `USB-C-TH_GT-USB-7055BB` | `0 0 3.685` |
| `CONN-TH_2P_L8.5-W9.2-H7.0-P3.81` | `-1.905 -0.025 0` |
| `RJ45-TH_GR01M1HXA001` | `-0.005 0.695 17.45` |
| `RJ45-TH_RRCH-5201-6P6C` | `0 -5.85 -0.2` |

`RJ45-TH_GR01M1HXA001` is the extreme case: its `.step` origin sits at the top
of the jack, so without the 17.45 mm lift the whole connector renders hanging
below the board.

Models not listed here needed no offset — their `.step` already seats correctly.

## Deriving an offset for a newly added part

The `.wrl` is the ground truth for placement. Read its bounding box (vertices
are in 0.1 inch units, so multiply by 2.54), read the real tessellated bounding
box of the placed `.step` from `kicad-cli pcb export glb`, and take the
difference. Verify by re-exporting and re-measuring rather than by eye — several
of these errors are a fraction of a millimetre and invisible in a render, but
they still land in the STEP handed to mechanical CAD.

# Project-owned 3D models

Models vendored here because no copy exists in `pcb/lib/EasyEDA` or the
`pcb/lib/JLCPCB-Kicad-Library` subtree, and `nix run .#kicad-locality` requires
every `(model ...)` reference to resolve through `${KIPRJMOD}`.

| File | Source | Licence |
| --- | --- | --- |
| `PinHeader_2x03_P2.54mm_Vertical.step` | KiCad official `kicad-packages3d`, `Connector_PinHeader_2.54mm.3dshapes/PinHeader_2x03_P2.54mm_Vertical.stpZ`, decompressed. Taken from the flake-pinned package, revision `c955b94c7b`. | CC-BY-SA 4.0 with the KiCad library exception |
| `ESP32-C6-WROOM-1.step` | [`espressif/kicad-libraries`](https://github.com/espressif/kicad-libraries) at commit `dd76561812ab300351234ba6e0ec1295641796f0`, path `3dmodels/espressif.3dshapes/ESP32-C6-WROOM-1.STEP`. sha256 `9565ee695edb06a09ae9a7017485ac54391e0ba9f0cab58609fd185e6351f4ac`. | CC-BY-SA 4.0 with the KiCad library exception |

Both licences carry the same exception the KiCad project uses: the copyright
holder waives article 3 for electronic designs that use the material, so
boards and generated fabrication files are unencumbered.

The `ESP32-C6-WROOM-1` placement values in
`pcb/lib/EasyEDA/EasyEDA.pretty/WIRELM-SMD_ESP32-C6-WROOM-1.kicad_mod` —
`(offset (xyz -9 -9.75 0))`, no rotation — are copied from Espressif's own
`footprints/Espressif.pretty/ESP32-C6-WROOM-1.kicad_mod`. Their pad origin
matches ours to within 0.01 mm, so the offset transfers unchanged.

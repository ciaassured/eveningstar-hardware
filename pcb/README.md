# EveningStar PCB

This directory contains the KiCad project for the EveningStar PCB.

## Reproducibility Goal

The PCB should remain openable from this repository in the future, even if
external KiCad libraries, plugin indexes, vendor APIs, or downloaded data
sources disappear or change shape.

The rule of thumb is:

- Project-specific symbols, footprints, and 3D models should be committed under
  `pcb/lib`.
- Third-party libraries that are used by the board should be vendored into this
  repository, not referenced through a local KiCad plugin path.
- External tools are acceptable when they are sufficiently pinned and
  recoverable. KiCad itself is provided through the root Nix flake and locked by
  `flake.lock`.
- KiCad stock symbols are referenced through `KICAD_SYMBOL_DIR`, which is set by
  the Nix tooling to the flake-pinned KiCad package.

If a part needs local customization, copy the symbol, footprint, or model into a
project-owned library and reference that copy.

## Nix Workflow

The root flake owns the lock file and imports the PCB-specific Nix module from
`pcb/nix`. Use the flake from the repository root.

Open a shell with the pinned KiCad version:

```sh
nix develop
```

The dev shell includes KiCad plus the project helper scripts. Inside the shell,
the scripts are available as `eveningstar-*` commands.

## Tool Reference

Run KiCad ERC and DRC, including warnings:

```sh
nix run .#drc
# or, inside nix develop:
eveningstar-drc
```

This writes `reports/erc.rpt` and `reports/drc.rpt`, prints both reports, and
exits non-zero if ERC or DRC reports violations.

Check for references to local, non-repo KiCad libraries or model paths:

```sh
nix run .#kicad-locality
# or, inside nix develop:
eveningstar-kicad-locality
```

This fails on absolute paths, KiCad third-party plugin variables, missing
repo-local 3D models, footprint library table entries outside `${KIPRJMOD}`, and
symbol library table entries outside `${KIPRJMOD}` or pinned `KICAD_SYMBOL_DIR`.

Check that the vendored JLCPCB subtree has not been edited directly:

```sh
nix run .#subtree-drift
# or, inside nix develop:
eveningstar-subtree-drift
```

This verifies `pcb/lib/JLCPCB-Kicad-Library` still matches the recorded subtree
squash commit and rejects uncommitted changes under that subtree.

Generate review artifacts:

```sh
nix run .#pcb-review
# or, inside nix develop:
eveningstar-pcb-review
```

This generates schematic PDF/SVG, board PDF/SVG, STEP, and GLB outputs under
`reports/review`. It is intended to be fast enough for CI.

Generate local PNG 3D renders:

```sh
nix run .#pcb-renders
# or, inside nix develop:
eveningstar-pcb-renders
```

This generates top, bottom, front, back, and isometric PNG renders under
`reports/review/renders`. It is intended for local use because KiCad 3D renders
are slow in CI.

Artifacts are written under `reports/`.

## CI Checks

Pull requests to `main` run `.github/workflows/kicad-drc.yml`.

The workflow:

- Installs Nix.
- Optionally configures Cachix.
- Runs the subtree drift check.
- Verifies the KiCad dev shell.
- Runs the repo-local reference check.
- Runs ERC and DRC.
- Generates and uploads review artifacts.

ERC/DRC and artifact generation run with `always()` so a failing locality check
still leaves useful reports on the PR.

## Library Layout

Vendored and project-owned libraries live under `pcb/lib`.

```text
pcb/lib/
  custom/
    symbols/
      custom_symbols.kicad_sym
  EasyEDA/
    symbols/
      EasyEDA.kicad_sym
    footprints/
      EasyEDA.pretty/
    3dmodels/
      EasyEDA.3dshapes/
  JLCPCB-Kicad-Library/
    symbols/
    footprints/
    3dmodels/
```

The KiCad library nicknames are kept stable in `sym-lib-table` and
`fp-lib-table`, so schematic references like `EasyEDA:...`,
`custom_symbols:...`, and `PCM_JLCPCB:...` remain readable.

## Development Plugins And Sources

This board has used external KiCad plugins and data sources during development:

- ImpartGUI
- JLCPCB Fabrication Toolkit
- `CDFER/JLCPCB-Kicad-Library`

Those tools are useful if you are actively adding or updating parts, generating
fabrication outputs, or syncing vendor metadata. Someone working on the board
will probably want them installed in their interactive KiCad setup.

They should not be required just to open, check, or review the project. Any
symbols, footprints, or 3D models required by the board should be present in
this repository, and KiCad itself should be obtained through Nix.

## Adding Parts

When adding a part from a plugin or external source:

1. Add or copy the required symbol, footprint, and 3D model into `pcb/lib`.
2. Reference files through `${KIPRJMOD}/lib/...`, not through
   `${KICAD*_3RD_PARTY}`, absolute paths, or plugin cache paths.
3. Run `nix run .#kicad-locality`.
4. Run `nix run .#drc`.

For the vendored JLCPCB subtree, do not edit files in
`pcb/lib/JLCPCB-Kicad-Library` directly. Update the subtree as a subtree, or
copy the asset into a project-owned library before customizing it.

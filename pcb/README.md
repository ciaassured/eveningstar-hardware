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

Entering the development shell installs or updates the repo's pre-commit hook
for the current clone. It can also be installed explicitly from the shell:

```sh
lefthook install
```

Git does not automatically trust and execute hooks from cloned repositories.
Entering `nix develop` is the developer's explicit trust step: the shell uses
the Nix-provided Lefthook to sync `.git/hooks`, so Nix remains the only tooling
dependency. Lefthook then runs the same Nix-backed check suite used by CI.

## Checks

Run every automated check:

```sh
nix run .#checks
# or, inside nix develop:
eveningstar-checks
```

The aggregate command runs all checks even if an earlier one fails, then exits
non-zero if any failed. It is the entry point used by Lefthook and GitHub
Actions.

The individual checks remain available for diagnosing a failure.

### ERC and DRC

Run KiCad ERC and DRC, including warnings:

```sh
nix run .#drc
# or, inside nix develop:
eveningstar-drc
```

This writes `reports/erc.rpt` and `reports/drc.rpt`, prints both reports, and
exits non-zero if ERC or DRC reports violations.

### Repo-local KiCad references

Check for references to local, non-repo KiCad libraries or model paths:

```sh
nix run .#kicad-locality
# or, inside nix develop:
eveningstar-kicad-locality
```

This fails on absolute paths, KiCad third-party plugin variables, missing
repo-local 3D models, footprint library table entries outside `${KIPRJMOD}`, and
symbol library table entries outside `${KIPRJMOD}` or pinned `KICAD_SYMBOL_DIR`.

### Vendored subtree drift

Check that the vendored JLCPCB subtree has not been edited directly:

```sh
nix run .#subtree-drift
# or, inside nix develop:
eveningstar-subtree-drift
```

This verifies `pcb/lib/JLCPCB-Kicad-Library` still matches the recorded subtree
squash commit and rejects uncommitted changes under that subtree.

## Review Tools

Review tools generate artifacts for a human to inspect or compare. They are
available through Nix, but are intentionally not run by Lefthook or CI.

Generate review artifacts:

```sh
nix run .#pcb-review
# or, inside nix develop:
eveningstar-pcb-review
```

This generates schematic PDF/SVG and 2D board PDF/SVG outputs under
`reports/review`.

Generate local 3D model exports:

```sh
nix run .#pcb-models
# or, inside nix develop:
eveningstar-pcb-models
```

This generates STEP and GLB outputs under `reports/review/3d-models`. It is
intended for local use because KiCad 3D model exports are slow in CI, but the
outputs are useful for mechanical CAD, enclosure checks, and richer PR review.

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

Pull requests to `main` run `.github/workflows/checks.yml`.

The workflow:

- Installs Nix.
- Optionally configures Cachix.
- Runs `nix run .#checks`, the same aggregate command used by Lefthook.
- Uploads ERC and DRC reports when they are generated.

The aggregate command attempts every check, so a failure in an earlier check
does not prevent ERC/DRC reports from being generated and uploaded.

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

- [ImpartGUI](https://github.com/Steffen-W/Import-LIB-KiCad-Plugin)
- [JLCPCB Fabrication Toolkit](https://github.com/bennymeg/Fabrication-Toolkit)
- [JLCPCB-Kicad-Library](https://github.com/CDFER/JLCPCB-Kicad-Library)

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
3. Run `nix run .#checks`.

For the vendored JLCPCB subtree, do not edit files in
`pcb/lib/JLCPCB-Kicad-Library` directly. Update the subtree as a subtree, or
copy the asset into a project-owned library before customizing it.

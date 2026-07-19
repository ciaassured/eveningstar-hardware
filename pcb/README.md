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

### Saved copper-zone fills

Check that every copper zone contains saved fill data on each of its layers:

```sh
nix run .#zones-filled
# or, inside nix develop:
eveningstar-zones-filled
```

After any board edit that can affect copper geometry, open the board in the
pinned KiCad PCB Editor, press <kbd>B</kbd> to refill all zones, and save before
committing. Production plotting uses the fills stored in the board, so this is
required even if DRC passes. The automated check detects absent saved fills; it
cannot prove that existing fills are current for the latest board edits.

### Vendored subtree drift

Check that the vendored JLCPCB subtree has not been edited directly:

```sh
nix run .#subtree-drift
# or, inside nix develop:
eveningstar-subtree-drift
```

This verifies `pcb/lib/JLCPCB-Kicad-Library` still matches the recorded subtree
squash commit and rejects uncommitted changes under that subtree.

## Publish Tools

Publish tools generate the complete artifact set for one hardware revision. They
are available through Nix, but are intentionally not run by Lefthook or CI.

Generate publish artifacts for the current checkout:

```sh
nix build --max-jobs auto .#publish
# or, to also link the result at reports/publish:
nix run .#publish
# inside nix develop:
eveningstar-publish
```

The command produces schematic and PCB PDFs/SVGs, deterministic 3D PNG renders,
a browser-optimized GLB, a STEP model, and JLCPCB production files. `nix build`
exposes the Nix store output through `result`; the command form also links that
immutable output at `reports/publish`. Because this is a derivation of the
filtered PCB source and pinned publishing tools, unchanged outputs are reused
from the local Nix store and can be shared through the configured Cachix cache.
Release metadata and changelog generation can be added to this same artifact
contract without changing the review workflow.

Generate only the JLCPCB production payload:

```sh
nix build .#production
# or, to also link the result at reports/production:
nix run .#production
# inside nix develop:
eveningstar-production
```

The production payload contains the Gerber/drill archive, BOM, placement list,
designator counts, and IPC-D-356 netlist. Its settings pin the Fabrication
Toolkit 5.3.1 JLCPCB placement translations used for V1. The build runs DRC and
schematic-parity validation, then plots the zone fills committed in the KiCad
board without refilling them. Fill and save zones in the pinned KiCad editor
after relevant design changes; plotting the reviewed stored fills avoids
nondeterministic polygon decomposition between independent KiCad processes.
Project-specific corrections live as hidden `FT Rotation Offset` fields on the
affected KiCad footprints; update them only after checking component pin 1
orientation against the datasheet and assembly preview. Generated timestamps,
ZIP entry metadata, permissions, and file order are normalized for reproducible
builds. The Toolkit source revision is pinned by the root `flake.lock` alongside
KiCad and the rest of the toolchain.
KiCad provides the underlying fabrication exporters; the pinned Toolkit is
retained for its JLCPCB-specific component-origin and rotation translations and
for compatibility with the production process used for the original board.

Production files are build artifacts and are not committed. Local output is
ignored under `pcb/production` and `reports`; published manufacturing files
belong in the GitHub release for the exact source tag that produced them. The
original as-ordered files remain available from the historical `v1.0.0` tag.

To force a fresh build and have Nix compare it with the existing store output:

```sh
nix build .#production --rebuild
```

The aggregate is assembled from independent schematic-document, PCB-document,
plan-render, side-render, isometric-render, GLB, STEP, and production
derivations. Nix can schedule those components in parallel and reuse them
individually. They are
also directly inspectable with commands such as `nix build .#render-plan` or
`nix build .#model-step`, without exposing additional imperative applications.

## Review Tools

Review tools generate artifacts for a human to inspect or compare. They are
available through Nix, but are intentionally not run by Lefthook or CI.

Generate a comparison from a pull request number or URL:

```sh
nix run .#review -- 31
# equivalent explicit form:
nix run .#review -- --pr 31
# URLs also work:
nix run .#review -- https://github.com/ciaassured/eveningstar-hardware/pull/31
# or, inside nix develop:
eveningstar-review 31
```

Compare any two locally available commits, branches, or tags by listing the
destination revision first and the source revision second:

```sh
nix run .#review -- v0.2.0 v0.3.0
nix run .#review -- main feature/new-layout
nix run .#review -- 2c5bf31 96e61e4
```

Compare a revision with the current working tree using `--worktree`. This
includes staged, unstaged, untracked, and deleted files, but excludes files
ignored by Git:

```sh
nix run .#review -- main --worktree
# HEAD is the default destination revision:
nix run .#review -- --worktree
```

For pull requests, the command resolves the exact source and destination
commits recorded by GitHub without changing or depending on the checkout. Git
revision comparisons archive the exact requested trees, while worktree
comparisons create an isolated temporary snapshot without switching branches or
modifying local files. Nix realizes the same publish derivation for either form.
Cached artifact sets are reused, then linked under
`reports/review` and compared through their browser-viewable SVG, PNG, and GLB
outputs. It serves the comparison on an ephemeral `127.0.0.1` port and prints
the URL; press Ctrl+C when the review is finished.
It also opens the URL in the default browser when a desktop opener is available;
the foreground server exits when interrupted and does not remain orphaned.
The view picker covers native vector schematic and board views, deterministic
KiCad 3D renders, and the interactive Three.js board model. Every view supports
overlay/reveal, side-by-side, pixel-difference, and highlighted-change modes.
Documents can be panned and zoomed without rasterizing SVGs; side-by-side
navigation can optionally be synchronized. Use <kbd>←</kbd> and <kbd>→</kbd> to
change view, <kbd>↑</kbd> and <kbd>↓</kbd> to change comparison mode, and
<kbd>[</kbd> and <kbd>]</kbd> to move through the current view's pages, layers,
images, or presets. Pull-request comparisons use `gh` for metadata and Git to
fetch missing commit objects; both are provided by Nix.

Generate the report without starting the local server:

```sh
nix run .#review -- --no-serve 31
nix run .#review -- --no-serve main --worktree
```

Because the review tool comes from the current checkout while the hardware
inputs come from the requested snapshots, a feature branch can test changes to
the review tooling against an existing PR or pair of revisions.

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

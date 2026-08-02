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

### Turntable animation

Build the looping turntable animation used to showcase the board:

```sh
nix build --max-jobs auto .#render-turntable
```

That leaves the usual `result` symlink, which is a garbage-collection root, so
the animation is at `result/EveningStar-turntable.webp`. It is not committed:
publish it by attaching it to the GitHub release, which the top-level
`README.md` embeds through the `releases/latest/download/` alias so the link
survives future releases untouched. Print the store path with
`nix build --print-out-paths` if something needs to consume the output without
relying on `result`.

`.#render-turntable` is an ordinary derivation of the filtered PCB source and
the pinned toolchain, so unchanged boards reuse the store output and can share
it through Cachix.

The output holds `EveningStar-turntable.webp`. The board stands on a narrow end
edge, leans 20°, and rides an upright turntable with the camera level, sweeping
front face to edge-on sliver to back face. The lean belongs to the board rather
than to the viewer, so it swings round with the spin: the component side is seen
from below, the bare copper side from above half a turn later, and the board
rocks from side to side through the edge-on quarters. The animation is 180 frames of a full
revolution at a 33 ms frame delay, so it runs at 30 fps and takes just under six
seconds to come round. It is encoded as an animated WebP with an alpha channel,
so it sits on light and dark README backgrounds alike.

At a 560x970 canvas that lands around 3.6 MB. `--frames`, `--width`,
`--height`, `--frame-delay`, and `--quality` are the knobs if that needs to come
down; WebP quality is already low enough that the frames are visually
indistinguishable from the source PNGs, so the frame count and canvas size are
where the remaining bytes are.

`kicad-cli pcb render --rotate` takes one set of Euler angles per image and
applies them X outermost, which puts the X rotation in view space. Leaning the
viewer is therefore the only lean it can express directly, and that reads as a
camera above a board which stays upright on screen. To lean the board instead,
each frame composes spin × lean × stand itself and decomposes the result back
into the angles KiCad expects. A spin of zero decomposes to exactly
`(tilt, 0, stand)`, which is a useful check that the composition is right.

The solder mask renders in JLCPCB blue rather than the KiCad default green,
selected with `--mask-colour`.

The value passed is `#123A7A`, far below the `#4990E2` usually quoted for
JLCPCB blue. KiCad renders the mask as a translucent layer over copper and
substrate, which lightens it substantially, so the number that goes in is not
the colour that comes out. Measured on the board face:

| `--mask-colour` | renders as |
| --------------- | ---------- |
| `#4990E2`       | `#68B6F0`  |
| `#2B6DCA`       | `#498FF0`  |
| `#1B4FA0`       | `#4270BB`  |
| `#123A7A`       | `#395D97`  |
| `#0D2A5C`       | `#344E7B`  |

Pick from the rendered column, not the input column. Go to `#0D2A5C` for a
deeper navy.

A colour reaches the 3D render only through the board stackup. `kicad-cli`
ignores KiCad's colour themes: a theme carrying a `3d_viewer` section is loaded
but never consulted by `pcb render`, at any schema version. This board has no
stackup at all, which is why it renders green by default. Writing one into
`EveningStar.kicad_pcb` would fix the colour, but a stackup is also fabrication
metadata — mask colour is an ordering attribute and the block carries dielectric
material and thicknesses — so the design file should only gain one when somebody
decides what to actually order.

The render therefore builds a throwaway copy of the board with a stackup
attached and renders that with `--use-board-stackup-colors`. The copy lives in a
directory of symlinks to the real project so `${KIPRJMOD}` still resolves the
project's footprints and 3D models, and the injected dielectric is sized so the
layers still total the 1.6 mm the board declares. Nothing is written back.

The intermediate PNG frames are not kept; only the encoded animation is.

The render is not bit-reproducible. KiCad resolves a few pixels differently
between runs on roughly one frame in fifty, one to five pixels out of the 1.7
million in a supersampled frame. That is invisible in the result but enough to
change the encoded bytes, so `nix build .#render-turntable --rebuild` will
sometimes report that the output differs. Forcing single-threaded software
rasterisation with `LP_NUM_THREADS=0` roughly halves the rate without removing
it, which points at KiCad's own draw order rather than the Mesa backend.

Because the animation is hosted rather than committed, a rebuild does not
disturb anything that is already published: re-upload only when the board has
changed visibly enough to be worth a new asset.

It is deliberately excluded from `.#publish`: the render is a showcase asset
rather than a release artifact, and it would otherwise add several minutes to
every publish.

KiCad fits each projection to the canvas individually, which would make the
board pulse in size and clip at the angles where its silhouette is widest. The
build therefore runs a low-resolution probe pass over the same angles, derives
one orthographic zoom that contains every silhouette, and holds it constant for
the render pass, so the framing follows board changes without manual tuning.
Probe silhouettes are measured against the requested canvas rather than the one
KiCad returns: KiCad renders into a canvas smaller than asked for, by a border
that shrinks as the request grows, while scaling the projection by the size it
was asked for. Measuring the returned canvas reads a different aspect at probe
scale than at render scale, which on this portrait canvas left the board at two
thirds of the height it should have filled.
Frames are rendered at twice the output size and downscaled with associated
alpha, and `--quality basic` is used because the higher quality settings bake a
floor shadow into the otherwise transparent background.

### Releases and hardware versioning

Release versions describe the hardware revision, not the volume or significance
of changes to the surrounding checks, rendering, review, or publishing tools.
Tooling-only changes do not normally require a hardware release.

- Increment the major version for an incompatible electrical, mechanical, or
  external-interface change.
- Increment the minor version for a backwards-compatible hardware capability or
  intentional circuit, component, or layout revision.
- Increment the patch version for corrections that preserve the intended
  circuit and interfaces, including fabrication-data, copper, keepout, and
  silkscreen fixes.

`v1.0.0` is a historical source tag and intentionally has no GitHub Release.
`v1.0.1` is the first release produced with the pinned, reproducible production
and publishing pipeline.

To prepare a release, first merge all intended changes to `main`, refill and
save copper zones after relevant board edits, and create a Markdown release
notes file. Review the changes and choose the version based primarily on the
schematics, board, and production outputs since the previous hardware tag:

```sh
nix run .#review -- v1.0.0 main
nix run .#release -- --dry-run v1.0.1 /path/to/release-notes.md
```

Inspect the rendered comparison and the staged assets under
`reports/release/v1.0.1/`. The dry run executes the complete checks and publish
build but does not create a tag or GitHub Release. When the result is ready to
publish, run:

```sh
nix run .#release -- v1.0.1 /path/to/release-notes.md
```

The release command requires a clean checkout of the latest `origin/main`,
rejects conflicting tags or releases, runs `nix run .#checks`, and builds the
full publish output locally. It stages a deterministic archive of every publish
artifact, individual production and 3D model files, and `SHA256SUMS`; then it
creates and pushes an annotated tag and creates the GitHub Release. If GitHub
release creation fails after the tag is pushed, correct the problem and rerun
the same command; an existing tag is accepted only when it identifies the same
`main` commit.

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
    custom_symbols.kicad_sym
  EasyEDA/
    EasyEDA.kicad_sym
    EasyEDA.pretty/
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

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

The output is exactly the set of GitHub release assets, in one flat directory
because releases hold no folders:

| File                         | Contents                                              |
| ---------------------------- | ----------------------------------------------------- |
| `EveningStar-gerbers.zip`    | Gerber and drill files for JLCPCB                     |
| `EveningStar-bom.csv`        | JLCPCB bill of materials                              |
| `EveningStar-cpl.csv`        | JLCPCB component placement list                       |
| `EveningStar-netlist.ipc`    | IPC-D-356 netlist for electrical test                 |
| `EveningStar-schematic.pdf`  | every schematic sheet                                 |
| `EveningStar-board.pdf`      | composite front and back views, then each layer       |
| `EveningStar-step.zip`       | STEP model of the assembled board, for enclosure CAD  |
| `EveningStar.glb`            | browser-optimized 3D model                            |
| `EveningStar-render-*.png`   | top, bottom, front, back, and isometric renders       |
| `EveningStar-turntable.webp` | the [turntable animation](#turntable-animation)       |
| `SHA256SUMS`                 | checksums of every other file                         |

Names carry no version, so `releases/latest/download/<name>` always links the
newest board, and the output depends only on the source rather than on the tag
it is released under. The production files are the `.#production` payload
renamed; its `designators.csv` is left out because it only repeats the BOM. The
per-sheet and per-layer SVGs are review artifacts rather than release assets,
built by `nix run .#review`.

`nix build` exposes the Nix store output through `result`; the command form also links that immutable output at
`reports/publish`. Because this is a derivation of the filtered PCB source and
pinned publishing tools, unchanged outputs are reused from the local Nix store
and can be shared through the configured Cachix cache. Release metadata and
changelog generation can be added to this same artifact contract without
changing the review workflow.

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
plan-render, side-render, isometric-render, turntable-render, GLB, STEP, and
production derivations. Nix can schedule those components in parallel and reuse
them individually. They are also directly inspectable with commands such as
`nix build .#render-plan` or `nix build .#model-step`, without exposing
additional imperative applications.

### Turntable animation

Build the looping turntable animation used to showcase the board:

```sh
nix build --max-jobs auto .#render-turntable
```

That leaves the usual `result` symlink, which is a garbage-collection root, so
the animation is at `result/EveningStar-turntable.webp`. It is not committed:
`.#publish` carries it as `EveningStar-turntable.webp`, and
`nix run .#release` attaches it to the GitHub release, which the top-level
`README.md` embeds through the `releases/latest/download/` alias so the link
survives future releases untouched. Print the store path with
`nix build --print-out-paths` if something needs to consume the output without
relying on `result`.

The render is a chain of derivations of the filtered PCB source and the pinned
toolchain, each reused from the store, and shareable through Cachix, while its
inputs are unchanged:

| Package              | Produces                                              |
| -------------------- | ----------------------------------------------------- |
| `.#board-glb`        | the board as fitted, as an uncompressed kicad-cli GLB |
| `.#turntable-frames` | one PNG per frame, rendered from it by Cycles         |
| `.#render-turntable` | `EveningStar-turntable.webp`, encoded from the frames |

`.#model-glb`, the browser model in the release, is `.#board-glb` compressed
with `gltfpack`. Changing the render script re-renders the frames without
re-exporting the board, and changing the encoding re-encodes without rendering.

The board stands upright on its bottom edge, the way round it is drawn, leans
20°, and rides a turntable in front of a level, still camera, sweeping front
face to edge-on sliver to back face. The lean belongs to the board rather than
to the viewer, so it swings round with the spin: the component side is seen from
above, the bare copper side from below half a turn later, and the board rocks
from side to side through the edge-on quarters. Key, fill, and rim area lights
stay put while the board turns, so shadows sweep across it as they would in a
studio. The animation is 180 frames of a full revolution at a 33 ms frame delay,
so it runs at 30 fps and takes just under six seconds to come round. It is
encoded as an animated WebP with an alpha channel, so it sits on light and dark
README backgrounds alike.

`pcb/nix/scripts/turntable.py` runs inside Blender. Its options are the knobs:
`--tilt` (`20` reverses the lean), `--stand` to turn the board within its own
plane before it is stood up, `--frames`, `--width`, `--height`, `--fill`,
`--focal-length`, `--samples`, and `--mask-colour`. `--only` renders just the
listed frames, which is the quick way to try a change:

```sh
nix build .#board-glb
nix shell --inputs-from . nixpkgs#blender -c blender -b --factory-startup \
  --python-exit-code 1 -P pcb/nix/scripts/turntable.py -- \
  --model result/EveningStar.glb --output reports/turntable --only 0,45,90
```

At a 760x720 canvas the animation lands around 4.5 MB. The WebP settings live in
the `.#render-turntable` derivation. Quality 65 is already low enough that the
frames are visually indistinguishable from the PNGs, and method 6 took around
forty times longer than method 4 on one core for about 4% smaller output, so the
frame count and canvas size are where the remaining bytes are.

The camera distance is solved once from the geometry, so that the widest point
of the whole revolution reaches `--fill` of the canvas and the board stays the
same size in every frame. Every vertex rides a circle of radius r at height z
about the spin axis. Seen from distance D, it reaches at most r / sqrt(D² − r²)
across the frame and |z| / (D − r) up or down, each scaled by the lens, so the
maximum over the vertices bounds the continuous revolution exactly, and a
bisection on D lands it on the fill.

kicad-cli gives the board layers materials of their own, on meshes named
`<board>_soldermask`, `<board>_pad`, and so on, and the script sets those to a
coated mask in `--mask-colour`, gold pads and vias, white silkscreen, and FR4.
Component models carry only a colour through the export, so they arrive at
glTF's defaults of fully metallic and fully rough, which renders plastic as dull
metal. These models paint bare metal in light neutral colours up to pure white:
leads, terminals, the magjack and ESP32 shields, and the electrolytic's can,
some with a blue cast. The script makes those and gold-ish ones polished metal,
and the dark and strongly coloured rest plastic. Metal needs something to
mirror, so the world behind the transparent film is a studio backdrop, bright
overhead and dark underfoot. Do-not-populate parts are left out of the export.
The frames use Blender's AgX view transform with its punchy look, which keeps
the mask a deep blue and the plastics dark under studio lights.

Cycles renders on the CPU, since the build sandbox has no GPU, at 32 samples
with denoising, which came within 45 dB PSNR of 64 samples at well under two
thirds of the time. One Blender process uses every core Nix grants the build;
splitting the frames across several processes measured no faster. With a fixed
seed the frames are reproducible: two runs on the same machine render identical
pixels. On a 32-core machine the frames take about nine minutes. Blender's
closure is about 3.8 GB, fetched once from the binary cache.

The render used to be done by `kicad-cli pcb render`, which cannot keep lights
still while the board turns. It builds its own lights fixed to the board and
ignores any in its settings, so cast shadows stayed glued to the board while its
view-following camera light, which casts none, moved the shading. Its framing
also took probe renders, since it fits each image to the canvas individually and
zooms in perspective by moving the camera.

Because the animation is hosted rather than committed, a rebuild does not
disturb anything that is already published. Each release attaches the animation
rendered from its own source, so the README always shows the latest released
board.

Including the animation in `.#publish` adds about nine minutes to a
publish whenever the board has changed, more on machines with fewer cores. It is
not part of the review artifacts, so `nix run .#review` does not render it.

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
full publish output locally. It checks that output against its `SHA256SUMS` and
stages it unchanged as the release assets; then it creates and pushes an
annotated tag and creates the GitHub Release. If GitHub release creation fails after the tag is pushed, correct the
problem and rerun the same command; an existing tag is accepted only when it
identifies the same `main` commit.

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

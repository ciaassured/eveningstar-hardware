# EveningStar Hardware Agent Guide

## Scope

These instructions apply to the entire repository.

## Project Context

This repository contains the hardware design for EveningStar, an isolated
ESP32-based Morningstar MeterBus interface. Firmware is maintained separately
at <https://github.com/ciaassured/eveningstar-firmware>; do not add firmware or
prototype application code here.

The design interfaces with battery and solar equipment and includes galvanic
isolation. Treat electrical, isolation, layout, and fabrication changes as
safety-relevant. Automated checks support review but do not replace engineering
review or physical validation.

## Repository Layout

- `pcb/`: KiCad project, hierarchical schematics, board, design rules, and
  project-local libraries.
- `pcb/lib/`: project-owned and vendored symbols, footprints, and 3D models.
- `pcb/nix/`: Nix packages and scripts for checks, publishing, and visual review.
- `pcb/production/`: committed manufacturing outputs for the current published
  design; update them only when explicitly preparing or updating a release.
- `docs/`: hardware references and ordering documentation.
- `reports/` and `result`: generated local outputs; both are ignored by Git.
- `flake.nix` and `flake.lock`: the authoritative pinned toolchain.

See `pcb/README.md` for the detailed KiCad, publishing, and review workflows.

## Toolchain and Commands

Run commands from the repository root. Prefer the pinned Nix tools over host
installations.

```sh
nix develop                 # Interactive KiCad/tooling shell
nix run .#checks            # Complete required validation suite
nix run .#drc               # KiCad ERC and DRC only
nix run .#kicad-locality    # Repository-local asset/reference checks
nix run .#subtree-drift     # Vendored JLCPCB subtree integrity
nix run .#publish           # Generate and link release artifacts
nix run .#review -- --worktree
```

`nix run .#checks` is the validation entry point used by Lefthook and GitHub
Actions. Run it before handing off any change. The aggregate deliberately runs
every check so that ERC and DRC reports are still produced after another
failure.

Publishing is intentionally not part of the pre-commit suite. When changing
publishing code or artifact-producing inputs, also run `nix run .#publish` or
the affected individual package and inspect the generated output.

## KiCad and Library Invariants

- Keep project-specific symbols, footprints, and 3D models under `pcb/lib`.
- References must resolve through `${KIPRJMOD}` or the Nix-provided
  `KICAD_SYMBOL_DIR`; do not commit workstation-specific absolute paths or
  plugin variables.
- Do not edit `pcb/lib/JLCPCB-Kicad-Library` directly. It is a recorded vendored
  subtree whose integrity is enforced by `nix run .#subtree-drift`.
- Copy parts that require customization into a project-owned library rather
  than modifying the vendored source.
- Keep library nicknames in `pcb/sym-lib-table` and `pcb/fp-lib-table` stable.
- Avoid broad textual rewrites of `.kicad_sch`, `.kicad_pcb`, and `.kicad_pro`
  files. Review structural diffs carefully and use the pinned KiCad version for
  edits whenever practical.
- Do not suppress new ERC or DRC findings merely to make validation pass.

## Change and Review Expectations

- Preserve unrelated working-tree changes and generated artifacts.
- Keep tooling behavior shared between local hooks and CI through the existing
  Nix-backed commands.
- For board or schematic changes, use the review workflow to inspect rendered
  source and destination artifacts in addition to reading the textual diff.
- Treat `pcb/production` changes as release-significant and review them against
  the source design that produced them.
- Use concise commit subjects in the existing `area: imperative summary` style,
  such as `pcb: ...`, `hardware: ...`, or `tooling: ...`.

set -euo pipefail

# Generate deterministic PCB review artifacts for CI pull requests.
#
# Outputs are written under reports/review and are intended for human review:
# schematic PDF/SVG, 2D board PDFs/SVGs, and STEP/GLB 3D models. PNG 3D renders
# are intentionally not generated here because KiCad render exports are slow in
# CI. The temporary KICAD*_3RD_PARTY variables are a compatibility shim for
# currently embedded model paths that still reference KiCad third-party library
# variables; kicad-locality.sh is the enforcement check that should eventually
# make that shim unnecessary.

review_dir="reports/review"
schematic_dir="$review_dir/schematic"
board_dir="$review_dir/board"
model_dir="$review_dir/3d-models"

rm -rf "$review_dir"
mkdir -p "$schematic_dir/svg" "$board_dir/pdf" "$board_dir/svg" "$model_dir"

third_party_dir="$(mktemp -d)"
trap 'rm -rf "$third_party_dir"' EXIT
mkdir -p "$third_party_dir/3dmodels"
ln -s "$PWD/pcb/lib/JLCPCB-Kicad-Library/3dmodels" \
  "$third_party_dir/3dmodels/com_github_CDFER_JLCPCB-Kicad-Library"
export KICAD10_3RD_PARTY="$third_party_dir"
export KICAD8_3RD_PARTY="$third_party_dir"
export KICAD_3RD_PARTY="$third_party_dir"

echo "::group::Schematic review exports"
kicad-cli sch export pdf \
  --exclude-pdf-property-popups \
  --output "$schematic_dir/EveningStar-schematic.pdf" \
  pcb/EveningStar.kicad_sch
kicad-cli sch export svg \
  --output "$schematic_dir/svg" \
  pcb/EveningStar.kicad_sch
echo "::endgroup::"

echo "::group::PCB 2D review exports"
kicad-cli pcb export pdf \
  --mode-single \
  --layers F.Cu,F.Mask,F.Silkscreen,F.Fab,Edge.Cuts \
  --output "$board_dir/pdf/EveningStar-front.pdf" \
  pcb/EveningStar.kicad_pcb
kicad-cli pcb export pdf \
  --mode-single \
  --mirror \
  --layers B.Cu,B.Mask,B.Silkscreen,B.Fab,Edge.Cuts \
  --output "$board_dir/pdf/EveningStar-back.pdf" \
  pcb/EveningStar.kicad_pcb
kicad-cli pcb export pdf \
  --mode-multipage \
  --layers F.Cu,In1.Cu,In2.Cu,B.Cu,F.Silkscreen,B.Silkscreen,F.Fab,B.Fab,Edge.Cuts \
  --output "$board_dir/pdf/layers" \
  pcb/EveningStar.kicad_pcb

kicad-cli pcb export svg \
  --mode-single \
  --fit-page-to-board \
  --layers F.Cu,F.Mask,F.Silkscreen,F.Fab,Edge.Cuts \
  --output "$board_dir/svg/EveningStar-front.svg" \
  pcb/EveningStar.kicad_pcb
kicad-cli pcb export svg \
  --mode-single \
  --fit-page-to-board \
  --mirror \
  --layers B.Cu,B.Mask,B.Silkscreen,B.Fab,Edge.Cuts \
  --output "$board_dir/svg/EveningStar-back.svg" \
  pcb/EveningStar.kicad_pcb
echo "::endgroup::"

echo "::group::PCB 3D model exports"
kicad-cli pcb export step \
  --force \
  --subst-models \
  --include-tracks \
  --include-pads \
  --include-zones \
  --include-silkscreen \
  --include-soldermask \
  --output "$model_dir/EveningStar.step" \
  pcb/EveningStar.kicad_pcb
kicad-cli pcb export glb \
  --force \
  --subst-models \
  --include-tracks \
  --include-pads \
  --include-zones \
  --include-silkscreen \
  --include-soldermask \
  --output "$model_dir/EveningStar.glb" \
  pcb/EveningStar.kicad_pcb
echo "::endgroup::"

find "$review_dir" -type f | sort

set -euo pipefail

# Generate local PNG 3D renders of the PCB.
#
# This is intentionally separate from pcb-review.sh because KiCad 3D rendering is
# slow in CI. Use this locally when visual inspection of the assembled board is
# useful; CI still generates the faster schematic/2D/STEP/GLB review artifacts.

render_dir="reports/review/renders"

rm -rf "$render_dir"
mkdir -p "$render_dir"

third_party_dir="$(mktemp -d)"
trap 'rm -rf "$third_party_dir"' EXIT
mkdir -p "$third_party_dir/3dmodels"
ln -s "$PWD/pcb/lib/JLCPCB-Kicad-Library/3dmodels" \
  "$third_party_dir/3dmodels/com_github_CDFER_JLCPCB-Kicad-Library"
export KICAD10_3RD_PARTY="$third_party_dir"
export KICAD8_3RD_PARTY="$third_party_dir"
export KICAD_3RD_PARTY="$third_party_dir"

echo "::group::PCB 3D render exports"
kicad-cli pcb render \
  --side top \
  --width 2400 \
  --height 1800 \
  --quality high \
  --background opaque \
  --output "$render_dir/top.png" \
  pcb/EveningStar.kicad_pcb
kicad-cli pcb render \
  --side bottom \
  --width 2400 \
  --height 1800 \
  --quality high \
  --background opaque \
  --output "$render_dir/bottom.png" \
  pcb/EveningStar.kicad_pcb
kicad-cli pcb render \
  --side front \
  --width 2400 \
  --height 1600 \
  --quality high \
  --background opaque \
  --output "$render_dir/front.png" \
  pcb/EveningStar.kicad_pcb
kicad-cli pcb render \
  --side back \
  --width 2400 \
  --height 1600 \
  --quality high \
  --background opaque \
  --output "$render_dir/back.png" \
  pcb/EveningStar.kicad_pcb
kicad-cli pcb render \
  --rotate "315,0,45" \
  --width 2400 \
  --height 1800 \
  --quality high \
  --background opaque \
  --output "$render_dir/isometric-front.png" \
  pcb/EveningStar.kicad_pcb
kicad-cli pcb render \
  --rotate "315,0,225" \
  --width 2400 \
  --height 1800 \
  --quality high \
  --background opaque \
  --output "$render_dir/isometric-back.png" \
  pcb/EveningStar.kicad_pcb
echo "::endgroup::"

find "$render_dir" -type f | sort

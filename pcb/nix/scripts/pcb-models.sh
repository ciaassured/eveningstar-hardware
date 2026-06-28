set -euo pipefail

# Generate local STEP and GLB 3D model exports of the PCB.
#
# This is intentionally separate from pcb-review.sh because KiCad 3D model
# exports are slow enough to be painful in CI. Use this locally when a reviewer,
# enclosure workflow, or mechanical CAD handoff needs an assembled board model.
# The temporary KICAD*_3RD_PARTY variables preserve compatibility with any
# embedded model paths that still reference KiCad third-party library variables.

model_dir="reports/review/3d-models"

rm -rf "$model_dir"
mkdir -p "$model_dir"

third_party_dir="$(mktemp -d)"
trap 'rm -rf "$third_party_dir"' EXIT
mkdir -p "$third_party_dir/3dmodels"
ln -s "$PWD/pcb/lib/JLCPCB-Kicad-Library/3dmodels" \
  "$third_party_dir/3dmodels/com_github_CDFER_JLCPCB-Kicad-Library"
export KICAD10_3RD_PARTY="$third_party_dir"
export KICAD8_3RD_PARTY="$third_party_dir"
export KICAD_3RD_PARTY="$third_party_dir"

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

find "$model_dir" -type f | sort

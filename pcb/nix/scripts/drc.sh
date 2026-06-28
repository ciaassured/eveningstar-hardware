set +e

# Run KiCad ERC and DRC in CI/local Nix with warnings promoted into the report
# and violation exit codes enabled. Both checks are run before exiting so CI can
# upload both reports even when ERC fails first.

mkdir -p reports

echo "::group::KiCad ERC"
kicad-cli sch erc \
  --severity-error \
  --severity-warning \
  --exit-code-violations \
  --format report \
  --output reports/erc.rpt \
  pcb/EveningStar.kicad_sch
erc_status=$?
cat reports/erc.rpt
echo "::endgroup::"

echo "::group::KiCad DRC"
kicad-cli pcb drc \
  --severity-error \
  --severity-warning \
  --schematic-parity \
  --exit-code-violations \
  --format report \
  --output reports/drc.rpt \
  pcb/EveningStar.kicad_pcb
drc_status=$?
cat reports/drc.rpt
echo "::endgroup::"

if [ "$erc_status" -ne 0 ] || [ "$drc_status" -ne 0 ]; then
  exit 1
fi

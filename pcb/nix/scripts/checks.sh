set -uo pipefail

# Run every automated repository check before returning a combined result.
# Keeping the orchestration here gives local hooks and CI the same entry point,
# while still allowing each check to be run on its own when debugging a failure.

status=0

run_check() {
  check_name="$1"
  shift

  echo
  echo "==> $check_name"

  if "$@"; then
    echo "==> $check_name passed"
  else
    check_status=$?
    echo "::error::$check_name failed (exit code $check_status)"
    status=1
  fi
}

run_check "Vendored subtree drift" eveningstar-subtree-drift
run_check "KiCad repo-local references" eveningstar-kicad-locality
run_check "KiCad saved copper-zone fills" eveningstar-zones-filled
run_check "KiCad ERC and DRC" eveningstar-drc

echo
if [ "$status" -eq 0 ]; then
  echo "All checks passed."
else
  echo "One or more checks failed."
fi

exit "$status"

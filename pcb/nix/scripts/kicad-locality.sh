set -euo pipefail

# Enforce that project-owned KiCad assets are reproducible from this repository.
#
# This intentionally allows stock KiCad symbols through KICAD_SYMBOL_DIR because
# default.nix points that variable at the flake-pinned KiCad package. Footprints,
# 3D models, and project/vendor libraries should resolve through KIPRJMOD so the
# board remains openable without relying on mutable local KiCad plugin paths.

status=0

report_bad() {
  title="$1"
  matches="$2"

  if [ -n "$matches" ]; then
    echo "::error::$title"
    echo "$matches"
    echo
    status=1
  fi
}

echo "::group::KiCad repo-local reference check"
echo "KiCad stock symbols via KICAD_SYMBOL_DIR are allowed because the flake pins the KiCad package."
echo "Project footprints, project models, and vendored third-party assets must resolve through KIPRJMOD."
echo

forbidden_kicad_vars="$(
  rg -n '\$\{KICAD[0-9_]*_3RD_PARTY\}|\$\{KICAD[0-9]*_3DMODEL_DIR\}|\$\{KICAD[0-9]*_FOOTPRINT_DIR\}' \
    pcb/EveningStar.kicad_pcb \
    pcb/fp-lib-table \
    pcb/lib/EasyEDA.pretty \
    || true
)"
report_bad "KiCad files reference external KiCad library/model variables" "$forbidden_kicad_vars"

absolute_model_paths="$(
  rg -n '^[[:space:]]*\(model "(/|[A-Za-z]:\\|~)' \
    pcb/EveningStar.kicad_pcb \
    pcb/lib/EasyEDA.pretty \
    || true
)"
report_bad "KiCad 3D model references use absolute or home-relative paths" "$absolute_model_paths"

all_model_refs="$(
  rg -n '^[[:space:]]*\(model "' \
    pcb/EveningStar.kicad_pcb \
    pcb/lib/EasyEDA.pretty \
    || true
)"
non_project_model_vars=""
if [ -n "$all_model_refs" ]; then
  non_project_model_vars="$(
    printf '%s\n' "$all_model_refs" \
      | rg '\$\{' \
      | rg -v '\$\{KIPRJMOD\}/' \
      || true
  )"
fi
report_bad "KiCad 3D model references use variables other than KIPRJMOD" "$non_project_model_vars"

missing_project_models=""
if [ -n "$all_model_refs" ]; then
  while IFS= read -r line; do
    [ -n "$line" ] || continue

    model_ref="${line#*\"}"
    model_ref="${model_ref%%\"*}"

    case "$model_ref" in
      \$\{KIPRJMOD\}/*)
        relative_path="${model_ref#\$\{KIPRJMOD\}/}"
        project_path="pcb/$relative_path"

        if [ ! -e "$project_path" ]; then
          missing_project_models="$missing_project_models
$line -> $project_path"
        fi
        ;;
    esac
  done <<< "$all_model_refs"
fi
report_bad "KiCad 3D model references point at missing repo files" "$missing_project_models"

fp_uris="$(rg -n '\(uri "' pcb/fp-lib-table || true)"
bad_fp_uris=""
if [ -n "$fp_uris" ]; then
  bad_fp_uris="$(
    printf '%s\n' "$fp_uris" \
      | rg -v '\(uri "\$\{KIPRJMOD\}/' \
      || true
  )"
fi
report_bad "Footprint library table contains non-repo URIs" "$bad_fp_uris"

sym_uris="$(rg -n '\(uri "' pcb/sym-lib-table || true)"
bad_sym_uris=""
if [ -n "$sym_uris" ]; then
  bad_sym_uris="$(
    printf '%s\n' "$sym_uris" \
      | rg -v '\(uri "\$\{KIPRJMOD\}/|\(uri "\$\{KICAD_SYMBOL_DIR\}/' \
      || true
  )"
fi
report_bad "Symbol library table contains URIs outside KIPRJMOD or pinned KICAD_SYMBOL_DIR" "$bad_sym_uris"

echo "::endgroup::"
exit "$status"

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: eveningstar-review [--no-serve] PR_NUMBER_OR_URL

Generate comparable PCB and schematic artifacts for the exact source and
destination commits recorded on a GitHub pull request, then serve the review
UI on 127.0.0.1, open it in a browser when possible, and run until interrupted.
Use --no-serve to only generate the report.
EOF
}

if [ "$#" -eq 1 ] && { [ "$1" = "--help" ] || [ "$1" = "-h" ]; }; then
  usage
  exit 0
fi

serve_review=true
if [ "${1:-}" = "--no-serve" ]; then
  serve_review=false
  shift
fi

if [ "$#" -ne 1 ]; then
  usage >&2
  exit 2
fi

pr_reference="$1"
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

pr_data="$(
  gh pr view "$pr_reference" \
    --json number,url,baseRefName,baseRefOid,headRefName,headRefOid \
    --jq '[.number,.url,.baseRefName,.baseRefOid,.headRefName,.headRefOid] | @tsv'
)"

IFS=$'\t' read -r \
  pr_number \
  pr_url \
  destination_branch \
  destination_commit \
  source_branch \
  source_commit \
  <<< "$pr_data"

if [ -z "$pr_number" ] || [ -z "$destination_commit" ] || [ -z "$source_commit" ]; then
  echo "error: GitHub returned incomplete metadata for '$pr_reference'" >&2
  exit 1
fi

ensure_commit() {
  commit="$1"
  fallback_ref="$2"

  if git cat-file -e "$commit^{commit}" 2>/dev/null; then
    return
  fi

  git fetch --no-tags origin "$commit" || git fetch --no-tags origin "$fallback_ref"

  if ! git cat-file -e "$commit^{commit}" 2>/dev/null; then
    echo "error: fetched '$fallback_ref' but could not resolve commit '$commit'" >&2
    exit 1
  fi
}

ensure_commit "$destination_commit" "refs/heads/$destination_branch"
ensure_commit "$source_commit" "refs/pull/$pr_number/head"

destination_short="$(git rev-parse --short "$destination_commit")"
source_short="$(git rev-parse --short "$source_commit")"
destination_label="$destination_branch ($destination_short)"
source_label="PR #$pr_number: $source_branch ($source_short)"

review_dir="$repo_root/reports/review"
rm -rf "$review_dir"
mkdir -p "$review_dir"

review_tmp_dir="$(mktemp -d)"
trap 'rm -rf "$review_tmp_dir"' EXIT
destination_tree="$review_tmp_dir/destination"
source_tree="$review_tmp_dir/source"
mkdir -p "$destination_tree" "$source_tree"

echo "Preparing PR #$pr_number review snapshots"
echo "  $pr_url"
echo "  destination: $destination_label"
echo "  source:      $source_label"
git archive "$destination_commit" | tar -x -C "$destination_tree"
git archive "$source_commit" | tar -x -C "$source_tree"

echo
echo "Realizing source and destination publish artifacts"
review_inputs="$(
  nix build \
    --extra-experimental-features nix-command \
    --max-jobs auto \
    --file "$EVENINGSTAR_REVIEW_INPUTS_EXPRESSION" \
    --arg destinationSource "$destination_tree" \
    --arg sourceSource "$source_tree" \
    --no-link \
    --print-out-paths
)"
ln -s "$review_inputs/destination" "$review_dir/destination"
ln -s "$review_inputs/source" "$review_dir/source"

node "$EVENINGSTAR_REVIEW_UI" \
  "$review_dir" \
  "$destination_label" \
  "$source_label"

echo
echo "Review comparison generated:"
echo "  $review_dir/index.html"

if [ "$serve_review" = true ]; then
  echo
  node "$EVENINGSTAR_REVIEW_SERVER" "$review_dir"
else
  echo "Run 'eveningstar-review $pr_reference' to generate and serve it."
fi

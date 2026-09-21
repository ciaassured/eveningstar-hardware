set -euo pipefail

usage() {
  cat <<'EOF'
Usage: eveningstar-release [--dry-run] <vMAJOR.MINOR.PATCH> <notes-file>

Build, tag, and publish an EveningStar hardware release from the latest main
commit. The notes file becomes the GitHub release body.

The command requires a clean main checkout, refreshes origin/main and tags,
runs the complete validation suite, builds the publish output, and stages it
unchanged as the release assets. The publish output is the release file for
file, SHA256SUMS included.

Use --dry-run to perform every step except creating/pushing the tag and creating
the GitHub release. Staged assets are left under reports/release/<tag>/.
EOF
}

dry_run=false
if [[ "${1:-}" == "--dry-run" ]]; then
  dry_run=true
  shift
fi

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ $# -ne 2 ]]; then
  usage >&2
  exit 2
fi

tag=$1
notes_file=$2

if [[ ! "$tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "error: release tag must have the form vMAJOR.MINOR.PATCH: $tag" >&2
  exit 2
fi

if [[ ! -f "$notes_file" ]]; then
  echo "error: release notes file does not exist: $notes_file" >&2
  exit 2
fi
notes_file="$(realpath "$notes_file")"

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

if [[ "$(git branch --show-current)" != "main" ]]; then
  echo "error: releases must be made from the main branch" >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "error: releases require a clean working tree" >&2
  git status --short >&2
  exit 1
fi

echo "Refreshing origin/main and release tags"
git fetch origin main --tags

head_commit="$(git rev-parse HEAD)"
main_commit="$(git rev-parse origin/main)"
if [[ "$head_commit" != "$main_commit" ]]; then
  echo "error: HEAD is not the latest origin/main commit" >&2
  echo "  HEAD:        $head_commit" >&2
  echo "  origin/main: $main_commit" >&2
  exit 1
fi

tagged_commit="$(git rev-parse -q --verify "refs/tags/$tag^{commit}" 2>/dev/null || true)"
if [[ -n "$tagged_commit" && "$tagged_commit" != "$head_commit" ]]; then
  echo "error: $tag already points to $tagged_commit, not $head_commit" >&2
  exit 1
fi

if gh release view "$tag" >/dev/null 2>&1; then
  echo "error: GitHub release $tag already exists" >&2
  exit 1
fi

echo "Running release checks for $head_commit"
"$EVENINGSTAR_CHECKS"

echo "Building publish artifacts"
"$EVENINGSTAR_PUBLISH"

publish_dir="$repo_root/reports/publish"
release_dir="$repo_root/reports/release/$tag"

# Check the publish output is whole before anything is tagged. The top-level
# README embeds the turntable through releases/latest/download/, so a release
# without it would break the README.
if [[ ! -f "$publish_dir/EveningStar-turntable.webp" ]]; then
  echo "error: publish output is missing the turntable animation" >&2
  exit 1
fi
(cd "$publish_dir" && sha256sum --check --quiet SHA256SUMS)

rm -rf "$release_dir"
mkdir -p "$release_dir"
cp --dereference "$publish_dir"/* "$release_dir/"

echo "Release assets staged under $release_dir"
find "$release_dir" -maxdepth 1 -type f -printf '  %f\n' | sort

if $dry_run; then
  echo "Dry run complete; no tag or GitHub release was created"
  exit 0
fi

if [[ -z "$tagged_commit" ]]; then
  git tag -a "$tag" -m "EveningStar $tag"
fi

if ! git ls-remote --exit-code --tags origin "refs/tags/$tag" >/dev/null 2>&1; then
  git push origin "$tag"
fi

assets=()
while IFS= read -r -d '' asset; do
  assets+=("$asset")
done < <(find "$release_dir" -maxdepth 1 -type f -print0 | sort -z)

gh release create "$tag" \
  "${assets[@]}" \
  --repo "$(gh repo view --json nameWithOwner --jq .nameWithOwner)" \
  --title "EveningStar $tag" \
  --notes-file "$notes_file" \
  --verify-tag

echo "Published EveningStar $tag from $head_commit"

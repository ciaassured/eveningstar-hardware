set -euo pipefail

# Verify the vendored JLCPCB library subtree has not been edited in place.
#
# The intended workflow is to update this directory only via git subtree. If a
# part needs customization, copy the symbol/footprint/model into a project-owned
# library and reference that copy instead. This check compares the vendored tree
# in HEAD with the recorded subtree squash commit and also rejects uncommitted
# worktree changes under the subtree path.

subtree_dir="pcb/lib/JLCPCB-Kicad-Library"

if [ ! -d "$subtree_dir" ]; then
  echo "::error::Expected subtree directory '$subtree_dir' does not exist"
  exit 1
fi

if ! git cat-file -e "HEAD:$subtree_dir"; then
  echo "::error::Expected subtree directory '$subtree_dir' is not present in HEAD"
  exit 1
fi

worktree_drift="$(git status --porcelain --untracked-files=all -- "$subtree_dir")"
if [ -n "$worktree_drift" ]; then
  echo "::error::Uncommitted or untracked non-ignored files found in '$subtree_dir'"
  echo
  echo "Do not edit files in '$subtree_dir' directly. Copy symbols/footprints/models"
  echo "into a project-owned library and reference that copy instead."
  echo
  echo "$worktree_drift"
  exit 1
fi

# Prefer the most recent marker reachable from HEAD, so a check running on one
# branch cannot pick up the subtree metadata of an unrelated branch. Searching
# every ref stays as a fallback for detached or partially fetched checkouts.
squash_commit="$(
  git log \
    HEAD \
    --grep="^git-subtree-dir: $subtree_dir$" \
    --format=%H \
    -n 1
)"

if [ -z "$squash_commit" ]; then
  squash_commit="$(
    git log \
      --all \
      --grep="^git-subtree-dir: $subtree_dir$" \
      --format=%H \
      -n 1
  )"
fi

if [ -z "$squash_commit" ]; then
  echo "::error::Could not find git-subtree metadata for '$subtree_dir'"
  echo "Run this check from a full clone. In CI, actions/checkout must use fetch-depth: 0."
  exit 1
fi

split_commit="$(
  git show -s --format=%B "$squash_commit" \
    | sed -n 's/^git-subtree-split: //p' \
    | tail -n 1
)"

# `git subtree` writes the vendored tree at the root of its squash commit, but a
# merge that flattens history (GitHub "Squash and merge" or "Rebase and merge")
# replays that commit as an ordinary repository commit, which leaves the
# git-subtree footers attached to a whole-repository tree instead. Both shapes
# record the same upstream state, so accept either one.
expected_refs="$squash_commit"
if git cat-file -e "$squash_commit:$subtree_dir" 2>/dev/null; then
  expected_refs="$squash_commit:$subtree_dir $expected_refs"
fi

expected_dir="$(mktemp -d)"
actual_dir="$(mktemp -d)"
trap 'rm -rf "$expected_dir" "$actual_dir"' EXIT

git archive "HEAD:$subtree_dir" | tar -x -C "$actual_dir"

matched_ref=""
diff_output=""
for expected_ref in $expected_refs; do
  rm -rf "${expected_dir:?}"
  mkdir -p "$expected_dir"
  git archive "$expected_ref" | tar -x -C "$expected_dir"

  if ref_diff="$(git diff --no-index --name-status -- "$expected_dir" "$actual_dir")"; then
    matched_ref="$expected_ref"
    break
  fi

  diff_output="$ref_diff"
done

if [ -z "$matched_ref" ]; then
  echo "::error::Vendored subtree drift detected in '$subtree_dir'"
  echo
  echo "The vendored JLCPCB subtree differs from its recorded subtree squash commit:"
  echo "  subtree commit: $squash_commit"
  if [ -n "$split_commit" ]; then
    echo "  upstream split: $split_commit"
  fi
  echo
  echo "Do not edit files in '$subtree_dir' directly. Copy symbols/footprints/models"
  echo "into a project-owned library and reference that copy instead."
  echo
  echo "Changed files:"
  echo "$diff_output" \
    | sed -e "s|$expected_dir/|recorded/|g" -e "s|$actual_dir/|worktree/|g"
  exit 1
fi

echo "Subtree '$subtree_dir' matches recorded subtree commit $squash_commit."
if [ -n "$split_commit" ]; then
  echo "Upstream split: $split_commit"
fi

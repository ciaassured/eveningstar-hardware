set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  eveningstar-review [--no-serve] PR_NUMBER_OR_URL
  eveningstar-review [--no-serve] --pr PR_NUMBER_OR_URL
  eveningstar-review [--no-serve] DESTINATION_REVISION SOURCE_REVISION
  eveningstar-review [--no-serve] [DESTINATION_REVISION] --worktree

Generate and compare the published hardware artifacts for two Git snapshots.

With one positional argument, the command retains its original pull-request
shorthand. Use --pr to make that form explicit. Two revisions compare any
locally resolvable commits, branches, or tags. --worktree compares a revision
(HEAD by default) with a snapshot of the current working tree, including staged,
unstaged, untracked, and deleted files while excluding Git-ignored files.

The review UI is served on 127.0.0.1 and opened in a browser when possible.
Use --no-serve to only generate the report.
EOF
}

fail_usage() {
  echo "error: $1" >&2
  echo >&2
  usage >&2
  exit 2
}

serve_review=true
pr_reference=""
compare_worktree=false
positional=()

while [ "$#" -gt 0 ]; do
  case "$1" in
    --help|-h)
      usage
      exit 0
      ;;
    --no-serve)
      serve_review=false
      shift
      ;;
    --pr)
      if [ "$#" -lt 2 ]; then
        fail_usage "--pr requires a pull request number or URL"
      fi
      if [ -n "$pr_reference" ]; then
        fail_usage "--pr may only be specified once"
      fi
      pr_reference="$2"
      shift 2
      ;;
    --pr=*)
      if [ -n "$pr_reference" ]; then
        fail_usage "--pr may only be specified once"
      fi
      pr_reference="${1#--pr=}"
      if [ -z "$pr_reference" ]; then
        fail_usage "--pr requires a pull request number or URL"
      fi
      shift
      ;;
    --worktree)
      compare_worktree=true
      shift
      ;;
    --)
      shift
      while [ "$#" -gt 0 ]; do
        positional+=("$1")
        shift
      done
      ;;
    -*)
      fail_usage "unknown option '$1'"
      ;;
    *)
      positional+=("$1")
      shift
      ;;
  esac
done

if [ -n "$pr_reference" ] && { [ "$compare_worktree" = true ] || [ "${#positional[@]}" -ne 0 ]; }; then
  fail_usage "--pr cannot be combined with revisions or --worktree"
fi

if [ -z "$pr_reference" ] && [ "$compare_worktree" = false ] && [ "${#positional[@]}" -eq 1 ]; then
  pr_reference="${positional[0]}"
  positional=()
fi

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

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

resolve_revision() {
  revision="$1"
  if ! git rev-parse --verify "$revision^{commit}" 2>/dev/null; then
    echo "error: '$revision' does not resolve to a local Git commit" >&2
    exit 1
  fi
}

revision_label() {
  revision="$1"
  commit="$2"
  short_commit="$(git rev-parse --short "$commit")"
  printf '%s (%s)' "$revision" "$short_commit"
}

snapshot_commit() {
  commit="$1"
  target="$2"
  git archive "$commit" | tar -x -C "$target"
}

snapshot_working_tree() {
  target="$1"
  deleted_files="$review_tmp_dir/worktree-deleted"
  overlay_files="$review_tmp_dir/worktree-overlay"

  snapshot_commit HEAD "$target"

  git diff --name-only -z --diff-filter=D --no-renames HEAD > "$deleted_files"
  while IFS= read -r -d '' relative_path; do
    rm -f -- "$target/$relative_path"
  done < "$deleted_files"

  git diff --name-only -z --diff-filter=d --no-renames HEAD > "$overlay_files"
  git ls-files --others --exclude-standard -z >> "$overlay_files"
  if [ -s "$overlay_files" ]; then
    tar -c --null --files-from="$overlay_files" -f - | tar -x -C "$target"
  fi
}

comparison_description=""
comparison_url=""
destination_commit=""
source_commit=""
destination_label=""
source_label=""
source_is_worktree=false

if [ -n "$pr_reference" ]; then
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

  ensure_commit "$destination_commit" "refs/heads/$destination_branch"
  ensure_commit "$source_commit" "refs/pull/$pr_number/head"

  destination_label="$destination_branch ($(git rev-parse --short "$destination_commit"))"
  source_label="PR #$pr_number: $source_branch ($(git rev-parse --short "$source_commit"))"
  comparison_description="PR #$pr_number review snapshots"
  comparison_url="$pr_url"
elif [ "$compare_worktree" = true ]; then
  if [ "${#positional[@]}" -gt 1 ]; then
    fail_usage "--worktree accepts at most one destination revision"
  fi

  destination_revision="${positional[0]:-HEAD}"
  destination_commit="$(resolve_revision "$destination_revision")"
  destination_label="$(revision_label "$destination_revision" "$destination_commit")"

  worktree_head="$(resolve_revision HEAD)"
  worktree_branch="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || printf 'detached HEAD')"
  worktree_short="$(git rev-parse --short "$worktree_head")"
  if [ -n "$(git status --porcelain --untracked-files=all)" ]; then
    worktree_state="modified"
  else
    worktree_state="clean"
  fi
  source_label="Working tree: $worktree_branch ($worktree_short, $worktree_state)"
  source_is_worktree=true
  comparison_description="revision and working-tree snapshots"
else
  if [ "${#positional[@]}" -ne 2 ]; then
    fail_usage "specify a PR, two revisions, or a destination revision with --worktree"
  fi

  destination_revision="${positional[0]}"
  source_revision="${positional[1]}"
  destination_commit="$(resolve_revision "$destination_revision")"
  source_commit="$(resolve_revision "$source_revision")"
  destination_label="$(revision_label "$destination_revision" "$destination_commit")"
  source_label="$(revision_label "$source_revision" "$source_commit")"
  comparison_description="Git revision snapshots"
fi

review_dir="$repo_root/reports/review"
rm -rf "$review_dir"
mkdir -p "$review_dir"

review_tmp_dir="$(mktemp -d)"
trap 'rm -rf "$review_tmp_dir"' EXIT
destination_tree="$review_tmp_dir/destination"
source_tree="$review_tmp_dir/source"
mkdir -p "$destination_tree" "$source_tree"

echo "Preparing $comparison_description"
if [ -n "$comparison_url" ]; then
  echo "  $comparison_url"
fi
echo "  destination: $destination_label"
echo "  source:      $source_label"
snapshot_commit "$destination_commit" "$destination_tree"
if [ "$source_is_worktree" = true ]; then
  snapshot_working_tree "$source_tree"
else
  snapshot_commit "$source_commit" "$source_tree"
fi

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
  echo "Run the same command without --no-serve to serve the review."
fi

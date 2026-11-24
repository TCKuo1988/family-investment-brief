#!/usr/bin/env bash
# Publish an allowlisted generated file without writing to the Pages source branch.
set -euo pipefail
file=$1
branch=$2
case "$file:$branch" in
  market-quotes.json:tck-market-data|line_preview.png:tck-line-images) ;;
  *) echo "Unexpected public artifact" >&2; exit 1 ;;
esac
ref="refs/heads/$branch"
remote=$(git ls-remote origin "$ref")
parents=()
if [[ -n "$remote" ]]; then
  git fetch -q --no-tags origin "$ref"
  parents=(-p FETCH_HEAD)
fi
index_dir=$(mktemp -d)
trap 'rm -rf "$index_dir"' EXIT
export GIT_INDEX_FILE="$index_dir/index"
blob=$(git hash-object -w "$file")
git update-index --add --cacheinfo "100644,$blob,$file"
tree=$(git write-tree)
commit=$(git -c user.name=github-actions -c user.email=41898282+github-actions[bot]@users.noreply.github.com \
  commit-tree "$tree" "${parents[@]}" -m "Publish $file")
git push -q origin "$commit:$ref"
printf '%s\n' "$commit"

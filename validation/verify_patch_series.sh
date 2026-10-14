#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 /path/to/vllm-checkout" >&2
  exit 2
fi

source_checkout=$1
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
upstream_revision=db9527a46873454610df6dbedf79a36d6bf1a7f6
temporary_root=$(mktemp -d)
trap 'rm -rf "$temporary_root"' EXIT

git -C "$source_checkout" archive "$upstream_revision" vllm | tar -x -C "$temporary_root"
(
  cd "$repo_root/patches"
  sha256sum --check series.sha256
)
cd "$temporary_root"
sha256sum --check "$repo_root/patches/upstream.sha256"
for patch_file in "$repo_root"/patches/*.patch; do
  patch --batch --forward -p1 --no-backup-if-mismatch --fuzz=0 < "$patch_file"
done
sha256sum --check "$repo_root/patches/runtime.sha256"
echo "deployment patch series matches the selected v0.31.0 runtime sources"

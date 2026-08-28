#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 /path/to/vllm-checkout" >&2
  exit 2
fi

source_checkout=$1
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
temporary_root=$(mktemp -d)
trap 'rm -rf "$temporary_root"' EXIT

git clone --shared "$source_checkout" "$temporary_root/patched"
git clone --shared "$source_checkout" "$temporary_root/expected"
git -C "$temporary_root/patched" checkout --detach v0.28.0
git -C "$temporary_root/expected" checkout --detach \
  be50f78ce62c7979ba7e552164cf4757d4ccce33

for patch_file in "$repo_root"/patches/*.patch; do
  patch -d "$temporary_root/patched" -p1 --no-backup-if-mismatch --fuzz=0 \
    < "$patch_file"
done

diff -ru "$temporary_root/expected/vllm" "$temporary_root/patched/vllm"

grep -q 'uses_grammar_constraint' \
  "$temporary_root/patched/vllm/sampling_params.py"

echo "deployment patch series matches the v0.28.0 V1 CC/MTP candidate"

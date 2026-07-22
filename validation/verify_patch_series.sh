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
git -C "$temporary_root/patched" checkout --detach v0.23.0
git -C "$temporary_root/expected" checkout --detach f49f4a1c5

for patch_file in "$repo_root"/patches/*.patch; do
  patch -d "$temporary_root/patched" -p1 --no-backup-if-mismatch --fuzz=0 \
    < "$patch_file"
done

diff -ru --exclude=sampling_params.py \
  "$temporary_root/expected/vllm" "$temporary_root/patched/vllm"

grep -q '_uses_grammar_constraint' \
  "$temporary_root/patched/vllm/sampling_params.py"

echo "deployment patch series matches vLLM candidate runtime plus patch 0001"

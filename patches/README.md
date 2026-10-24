# vLLM v0.31.0 deployment patches

Apply these patches in filename order to upstream commit
`db9527a46873454610df6dbedf79a36d6bf1a7f6`:

- `0001`: explicit-copy fallback when CC prevents a live host/device alias.
- `0002`: reject public structured-output regex constraints.
- `0003`: repetition defaults for grammar-constrained output, preserving opt-out.
- `0004`: bounded first-layer RMS policy for BF16 Gemma on H200.
- `templates/0005`: explicit non-thinking answer prefix after tool results.

MRV2 replaces the V1 metadata, block-table, and output-publication patch stack.
The RMS policy preserves the selected reduction behavior; it does not imply
an independently measured speedup or general numerical equivalence.

`series.sha256`, `upstream.sha256`, and `runtime.sha256` verify patch bytes and
source files before and after application. Both the Docker build and
`validation/verify_patch_series.sh /path/to/vllm-checkout` enforce these hashes
and apply patches with zero fuzz.

Template patches use separate source hashes because the image keeps examples
under `/vllm-workspace`, outside the installed Python package.

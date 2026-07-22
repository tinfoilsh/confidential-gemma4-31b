# Validation

`verify_patch_series.sh` checks the deployment patches against an exact vLLM
v0.23.0 checkout and compares the resulting runtime package to the preserved
candidate.

`validate_stock_candidate_cc.py` runs the deterministic seven-case API suite
against stock and candidate endpoints. Run it inside the benchmark environment
where both endpoints are available; see `--help` for arguments.

Correctness results must be preserved in `vllm-cc-gemma4-lab`, not committed
to this deployment repository.

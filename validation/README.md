# Validation

`verify_patch_series.sh` applies the deployment patches to exact vLLM v0.25.1
and compares the runtime package to source commit `613cb3f8d`.

`validate_stock_candidate_cc.py` runs the deterministic seven-case API suite
against stock and candidate endpoints. Run it inside the benchmark environment
where both endpoints are available; see `--help` for arguments.

`validate_endpoint.py` runs the same seven cases repeatedly against one
endpoint. It also checks deterministic normalized output and is the preferred
runner for one-GPU sequential stock/candidate validation.

`stress_endpoint.py` builds a serial oracle for every API case, then shuffles
the cases across concurrent workers. It checks the absolute expectations and
equality with the oracle while request slots are reused.

`test_block_table_coalescing.py` runs a randomized property test against the
installed candidate runtime. It verifies that coalesced destinations are
disjoint and reproduce the final authoritative CPU block table.

`validate_security_endpoint.py` exercises the public-input trust boundary. It
expects regex constraints, remote and local-file media, video, and negative
prompt token IDs to be rejected; checks inline image handling; churns canceled
streams; and verifies health and canary isolation afterward.

`validate_responses_endpoint.py` covers streamed text, forced and parallel
streamed tools, function-result continuation, and streamed inline-image input.

Correctness results must be preserved in `vllm-cc-gemma4-lab`, not committed
to this deployment repository.

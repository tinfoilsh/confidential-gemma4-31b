# Validation

`verify_patch_series.sh` applies the deployment patches to exact vLLM v0.31.0
and verifies the selected runtime's source hashes. The Docker build runs the
existing UVA fallback and Gemma request-policy CPU tests; CUDA cases are skipped
when no GPU is available.

`test_gemma_template.py` checks tool-result answer boundaries, thinking modes,
and user follow-ups. Set `GEMMA_CHAT_TEMPLATE` to a patched template path when
running it outside the container; the Docker build tests the deployed template.

`test_gemma_mm_prefix.py` checks that large image-attention ranges survive on
models that clamp them inside the kernel, while preserving the size limit for
other models. It runs in the Docker build with the patched runtime.

`validate_stock_candidate_cc.py` runs the deterministic seven-case API suite
against stock and candidate endpoints. Run it inside the benchmark environment
where both endpoints are available; see `--help` for arguments.

`validate_endpoint.py` runs the same seven cases repeatedly against one
endpoint. It also checks deterministic normalized output and is the preferred
runner for one-GPU sequential stock/candidate validation.

`stress_endpoint.py` builds a serial oracle for every API case, then shuffles
the cases across concurrent workers. It checks the absolute expectations and
equality with the oracle while request slots are reused.

`test_block_table_coalescing.py` is retained for the v0.25.1 rollback runtime.
It verifies that coalesced destinations are disjoint and reproduce the final
authoritative CPU block table.

`validate_security_endpoint.py` exercises the public-input trust boundary. It
expects regex constraints, remote and local-file media, video, and negative
prompt token IDs to be rejected; checks inline image handling; churns canceled
streams; and verifies health and canary isolation afterward.

`validate_responses_endpoint.py` covers streamed text, forced and parallel
streamed tools, function-result continuation, and streamed inline-image input.

Do not commit correctness results to this deployment repository.

# confidential-gemma4-31b

Tinfoil config repo for running `google/gemma-4-31B-it` with `vllm` on a single B200 confidential VM at the model's full 256K context length.

Update [`tinfoil-config.yml`](./tinfoil-config.yml) with the final modelpack hash once it is available. The `--model` path uses the first underscore-delimited segment of the `mpk` value.

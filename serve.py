"""Select Gemma GPU defaults before starting the inference sidecar."""

import argparse
import json
import os
import sys

BLACKWELL_CAPABILITY_MAJOR = 10
B300_CAPABILITY = (10, 3)
ATTENTION_BACKEND_FLAG = "--attention-backend"
DEFAULT_ATTENTION_BACKEND = "FLASH_ATTN"
B300_ATTENTION_BACKEND = "TRITON_FLASHINFER"
SPECULATIVE_TOKENS_FLAG = "--spec-tokens"
DEFAULT_SPECULATIVE_TOKENS = 4
B300_SPECULATIVE_TOKENS = 6
SERVING_COMMAND = ("/opt/tinfoil/inference-sidecar", "vllm", "serve")


def serving_command(arguments, capability):
    arguments = list(arguments)
    flags = {argument.split("=", 1)[0].replace("_", "-")
             for argument in arguments if argument.startswith("--")}
    if ATTENTION_BACKEND_FLAG not in flags:
        if capability == B300_CAPABILITY:
            arguments.extend([ATTENTION_BACKEND_FLAG, B300_ATTENTION_BACKEND])
        elif capability[0] != BLACKWELL_CAPABILITY_MAJOR:
            arguments.extend([ATTENTION_BACKEND_FLAG, DEFAULT_ATTENTION_BACKEND])

    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--speculative-config", "--speculative_config", "-sc", type=json.loads)
    parser.add_argument(SPECULATIVE_TOKENS_FLAG, "--spec_tokens")
    options, _ = parser.parse_known_args(arguments)
    config = options.speculative_config
    if (isinstance(config, dict) and config.get("method") == "mtp"
            and "num_speculative_tokens" not in config
            and "num-speculative-tokens" not in config
            and options.spec_tokens is None
            and not any(flag.startswith("--speculative-config.") for flag in flags)):
        count = B300_SPECULATIVE_TOKENS if capability == B300_CAPABILITY else DEFAULT_SPECULATIVE_TOKENS
        arguments.extend([SPECULATIVE_TOKENS_FLAG, str(count)])
    return [*SERVING_COMMAND, *arguments]


def main():
    import torch

    command = serving_command(sys.argv[1:], torch.cuda.get_device_capability())
    os.execv(command[0], command)


if __name__ == "__main__":
    main()

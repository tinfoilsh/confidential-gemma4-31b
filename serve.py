"""Select the Gemma attention default before starting the inference sidecar."""

import os
import sys

BLACKWELL_CAPABILITY_MAJOR = 10
ATTENTION_BACKEND_FLAG = "--attention-backend"
DEFAULT_ATTENTION_BACKEND = "FLASH_ATTN"
SERVING_COMMAND = ("/opt/tinfoil/inference-sidecar", "vllm", "serve")


def serving_command(arguments, capability_major):
    arguments = list(arguments)
    explicit_backend = any(
        argument == ATTENTION_BACKEND_FLAG
        or argument.startswith(ATTENTION_BACKEND_FLAG + "=")
        for argument in arguments
    )
    if capability_major != BLACKWELL_CAPABILITY_MAJOR and not explicit_backend:
        arguments.extend([ATTENTION_BACKEND_FLAG, DEFAULT_ATTENTION_BACKEND])
    return [*SERVING_COMMAND, *arguments]


def main():
    import torch

    command = serving_command(sys.argv[1:], torch.cuda.get_device_capability()[0])
    os.execv(command[0], command)


if __name__ == "__main__":
    main()

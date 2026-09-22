# Gemma 4 Vision Budget Repro and Fix

## Problem

The Gemma 4 deployment in this repo currently starts vLLM without any multimodal processor override:

- [`tinfoil-config.yml`](./tinfoil-config.yml) does not pass `--mm-processor-kwargs`
- vLLM's Gemma 4 recipe documents `280` soft tokens per image as the default
- OCR and handwriting localization improve materially when Gemma 4 is given a higher per-image token budget

The checked-in deployment today is:

```yaml
containers:
  - name: "gemma4-31b"
    image: "vllm/vllm-openai:gemma4-cu130@sha256:9f82491807fccb4c7a9e767cdf3c3648a80d98b4e7d345cfa011e8ddc5eb2098"
    command: [
      "--model", "/tinfoil/mpk/mpk-0900ca6b913db0036792149d3ea5862986d66a6964b010e998f56fbb7e1276ab",
      "--tensor-parallel-size", "1",
      "--max-model-len", "262144",
      "--gpu-memory-utilization", "0.95",
      "--served-model-name", "gemma4-31b",
      "--enable-auto-tool-choice",
      "--tool-call-parser", "gemma4",
      "--reasoning-parser", "gemma4",
      "--limit-mm-per-prompt", "{\"image\": 4, \"audio\": 1, \"video\": 1}",
      "--async-scheduling",
      "--port", "8001"
    ]
```

So the current deployment is already using the Gemma 4-specific image and parser flags. The missing piece is just the vision-budget setting when clients do not send one themselves.

The attached overlays in `../gemma-tests/` are consistent with that:

- `tinfoil-hosted-handwriting-smaller.gemma4-31b.DEFAULT.png` shows the low-budget result
- `google-hosted-handwriting-smaller.gemma-4-31b-it.MEDIA_RESOLUTION_MEDIUM.png` is noticeably better
- `google-hosted-handwriting-smaller.gemma-4-31b-it.MEDIA_RESOLUTION_HIGH.png` is much better

The closest vLLM equivalent to Google's `mediaResolution` setting is `mm_processor_kwargs.max_soft_tokens`:

- `560` is the closest "medium-like" budget
- `1120` is the closest "high-like" budget

That mapping is an inference from the published token ladders, not an API contract.

## What To Reproduce

Re-run the same handwriting/OCR benchmark against the current checked-in deployment, with the same prompt, same input image, and only one variable changed:

1. Current deployment behavior: no `mm_processor_kwargs`
2. Medium-like behavior: `mm_processor_kwargs.max_soft_tokens = 560`
3. High-like behavior: `mm_processor_kwargs.max_soft_tokens = 1120`

For an exact apples-to-apples result, use the original benchmark input page and scorer. The PNGs under `../gemma-tests/` are output visualizations, not the source page.

If the original benchmark image is unavailable, you can still verify that the parameter plumbing works with any local image, including one of the PNGs already in `../gemma-tests/`. That is enough to prove whether Tinfoil is honoring `mm_processor_kwargs`, but not enough to reproduce the published benchmark scores.

## What We Verified On The Live Deployment

Using the live Tinfoil endpoint on 2026-04-14 with the checked-in deployment, the same local image and the same prompt produced:

- default: `prompt_tokens = 289`
- explicit `280`: `prompt_tokens = 289`
- explicit `560`: `prompt_tokens = 563`
- explicit `1120`: `prompt_tokens = 1087`

The `default` and explicit `280` cases matched exactly, which is strong evidence that the current deployment default is `280`.

The `560` and `1120` cases increased prompt tokens substantially, which proves the live endpoint is already honoring client-supplied `mm_processor_kwargs`.

The exact prompt-token count does not have to equal the requested ceiling, because Gemma 4 strips some padding after preprocessing and the realized token count depends on image geometry.

## Quick API Repro

Set:

```bash
export BASE_URL="${BASE_URL:-https://inference.tinfoil.sh/v1}"
export MODEL="${MODEL:-gemma4-31b}"
export TINFOIL_API_KEY="..."
export INPUT_IMAGE="/absolute/path/to/the-original-handwriting-page.png"
```

If you do not have the original benchmark image, use one of the local repo PNGs as a smoke test instead, for example:

```bash
export INPUT_IMAGE="/Users/tanya/tinfoil/functions/gemma-tests/tinfoil-hosted-handwriting-smaller.gemma4-31b.DEFAULT.png"
```

Then run:

```python
import base64
import json
import os
import urllib.request

base_url = os.environ["BASE_URL"].rstrip("/")
model = os.environ["MODEL"]
api_key = os.environ["TINFOIL_API_KEY"]
input_image = os.environ["INPUT_IMAGE"]

with open(input_image, "rb") as f:
    image_url = "data:image/png;base64," + base64.b64encode(f.read()).decode()

prompt = (
    "Locate each handwritten line on the page and return JSON with one item per "
    "line. Each item must include the text and a bounding box."
)

def run_case(label, max_soft_tokens=None):
    body = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "max_tokens": 1024,
        "temperature": 0,
    }
    if max_soft_tokens is not None:
        body["mm_processor_kwargs"] = {"max_soft_tokens": max_soft_tokens}

    req = urllib.request.Request(
        base_url + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        payload = json.loads(resp.read())
    text = payload["choices"][0]["message"]["content"]
    print(f"\n--- {label} ---\n{text[:4000]}\n")

run_case("default")
run_case("explicit_280", 280)
run_case("medium_like_560", 560)
run_case("high_like_1120", 1120)
```

Expected outcome:

- `default` and explicit `280` should match
- `560` and `1120` should increase prompt token usage relative to default
- with the original benchmark image, `560` and especially `1120` should improve small-text handling

Run these serially while reproducing quality. Do not mix different budgets concurrently in the same pool until the upstream Gemma 4 mixed-resolution crash is fixed.

Prefer local data URLs over remote image URLs for repros. In practice, backend URL fetching may fail depending on the serving environment's outbound access policy.

## tinfoil-python Repro

There is also a runnable Python script in this directory:

- [`gemma_repro_tinfoil_python.py`](./gemma_repro_tinfoil_python.py)

It is intentionally short for Colab use. It uses `TinfoilAI`, takes an image path plus an optional prompt, and prints the result for `default`, `280`, `560`, and `1120`.

Good real handwritten page to test with:

- Library of Congress item page: <https://www.loc.gov/pictures/item/2023637795/>
- Direct large JPEG for pages 2-3: <https://tile.loc.gov/storage-services/service/pnp/ppmsca/86400/86484v.jpg>

This is a useful test page because it is real handwriting, public domain, and dense enough that the model's output changes materially as the vision budget changes.

In a Colab cell:

```bash
export TINFOIL_API_KEY="..."
UV_CACHE_DIR=/tmp/uv-cache \
uv run --project /Users/tanya/tinfoil/functions/tinfoil-python \
  python /Users/tanya/tinfoil/functions/confidential-gemma4-31b/gemma_repro_tinfoil_python.py \
  https://tile.loc.gov/storage-services/service/pnp/ppmsca/86400/86484v.jpg \
  "Transcribe the first 12 handwritten lines exactly as they appear. Output plain text only."
```

If you have the original benchmark image, use that URL or file path instead of the Library of Congress URL.

The script fetches the image client-side and sends a data URL to Tinfoil. That is more reliable than asking the backend to fetch the image itself. If `uv` cannot write to its default cache path, setting `UV_CACHE_DIR=/tmp/uv-cache` keeps the cache in writable space.

On 2026-04-14, this Library of Congress page produced visibly different transcriptions between `default` and the higher-budget runs on the live Tinfoil deployment. The gap was obvious enough to use as a manual smoke test, even though the "best" budget on this particular transcription prompt was not perfectly monotonic.

## Bash Repro

If you just want something runnable, use the bash scripts in this directory:

- [`gemma_repro_single.sh`](./gemma_repro_single.sh)
- [`gemma_repro_compare.sh`](./gemma_repro_compare.sh)

They already have the current API key embedded as the default, but `TINFOIL_API_KEY` still overrides it.

### Quick compare

```bash
./confidential-gemma4-31b/gemma_repro_compare.sh
```

This runs the Library of Congress handwritten page through:

- `default`
- `280`
- `560`
- `1120`

and prints:

- `prompt_tokens`
- `completion_tokens`
- the first part of the model output

What to look for:

- `default` and `280` should match or be very close
- `560` and `1120` should have materially higher `prompt_tokens`
- the text output should visibly change as the budget changes

On the live deployment, the verified smoke-test output was:

- `default`: `prompt_tokens 275`
- `280`: `prompt_tokens 275`
- `560`: `prompt_tokens 569`
- `1120`: `prompt_tokens 1096`

That confirms the client-side budget control is active.

### Single transcription run

```bash
./confidential-gemma4-31b/gemma_repro_single.sh
```

By default this uses:

- the same Library of Congress handwritten image
- `BUDGET=560`
- a transcription prompt for the first 12 lines

You can override the budget:

```bash
BUDGET=1120 ./confidential-gemma4-31b/gemma_repro_single.sh
```

You can also pass a different image URL and prompt:

```bash
./confidential-gemma4-31b/gemma_repro_single.sh \
  "https://tile.loc.gov/storage-services/service/pnp/ppmsca/86400/86484v.jpg" \
  "Transcribe the first 12 handwritten lines exactly as they appear. Output plain text only."
```

### What To Watch Out For

1. Look at quality, not just token counts.
   Higher `prompt_tokens` only proves the larger vision budget was used. It does not prove the result is better.

2. The best budget may not be perfectly monotonic on every page.
   On OCR-heavy pages, `1120` is often the strongest setting, but on some pages or prompts `560` can look better.

3. Use the original benchmark image for the real evaluation.
   The Library of Congress page is a good smoke test, but it is not the same page that produced the original score gap.

4. Remote image fetches can fail for environmental reasons.
   The scripts fetch the image client-side and send a `data:` URL, which is more reliable than asking the model backend to fetch the URL itself.

5. You may hit transient DNS issues on `tile.loc.gov`.
   If that happens, rerun the script. The script logic is fine; we saw one sandbox-only DNS failure while testing.

6. Do not mix budgets concurrently in one production pool if you care about stability.
   The current upstream Gemma 4 mixed-resolution issue is still relevant.

## Benchmark Repro

If you already have the scorer that produced:

- `23.2` for Google `MEDIA_RESOLUTION_MEDIUM`
- `73.4` for Google `MEDIA_RESOLUTION_HIGH`
- `11.2` for Tinfoil default

then the minimal repro is:

1. Keep the benchmark image, prompt, and evaluator unchanged.
2. Point the harness at the current `gemma4-31b` deployment.
3. Run once with no `mm_processor_kwargs`.
4. Run once with `mm_processor_kwargs={"max_soft_tokens": 560}`.
5. Run once with `mm_processor_kwargs={"max_soft_tokens": 1120}`.
6. Compare score deltas and the rendered overlays.

That isolates the issue to vision token budget rather than model weights, prompt wording, or routing.

## Fix Options

### Option A: Set a Better Default for This Deployment

If the goal is "Gemma 4 should be good at OCR by default even when clients do nothing special," make the server default higher.

Patch the current command in [`tinfoil-config.yml`](./tinfoil-config.yml) like this:

```diff
       "--tool-call-parser", "gemma4",
       "--reasoning-parser", "gemma4",
       "--limit-mm-per-prompt", "{\"image\": 4, \"audio\": 1, \"video\": 1}",
+      "--mm-processor-kwargs", "{\"max_soft_tokens\": 1120}",
       "--async-scheduling",
       "--port", "8001"
```

Use `560` instead of `1120` if latency or cost matters more than OCR quality.

This is the safest production fix today because every request in the pool uses the same vision budget.

### Option B: Expose It Per Request

vLLM's OpenAI-compatible APIs already accept `mm_processor_kwargs`, and the router in this repo only strips `priority`; it does not remove `mm_processor_kwargs`.

This means the server flag is not required if every relevant client already sends `mm_processor_kwargs` explicitly.

Raw JSON request:

```json
{
  "model": "gemma4-31b",
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
        {"type": "text", "text": "Locate each handwritten line and return bounding boxes."}
      ]
    }
  ],
  "max_tokens": 1024,
  "mm_processor_kwargs": {
    "max_soft_tokens": 1120
  }
}
```

OpenAI Python client:

```python
from openai import OpenAI

client = OpenAI(base_url="https://inference.tinfoil.sh/v1", api_key="...")

resp = client.chat.completions.create(
    model="gemma4-31b",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": IMAGE_URL}},
                {"type": "text", "text": "Locate each handwritten line and return bounding boxes."},
            ],
        }
    ],
    max_tokens=1024,
    extra_body={"mm_processor_kwargs": {"max_soft_tokens": 1120}},
)
```

This is enough to control the vision budget from the client side today.

Use it only if the backing vLLM build is new enough and you can tolerate the current mixed-budget concurrency risk.

### Option C: Separate Pools by Budget

If you need both fast/default traffic and high-detail OCR traffic, split them into separate deployments instead of mixing budgets in one replica pool.

Example:

- `gemma4-31b` -> fixed `max_soft_tokens = 560`
- `gemma4-31b-ocr` -> fixed `max_soft_tokens = 1120`

That avoids the current upstream issue where concurrent Gemma 4 image requests with different budgets can crash the server.

## Recommended Path

For this repo, the decision is:

1. If all OCR callers can send `mm_processor_kwargs`, client-side control is sufficient.
2. If you want OCR-friendly behavior by default, set a fixed default budget in [`tinfoil-config.yml`](./tinfoil-config.yml).
3. Use `1120` if handwriting/OCR quality is the priority.
4. If multiple budgets are needed, split them into separate deployments instead of mixing them in one pool.

## References

- vLLM Gemma 4 recipe: <https://docs.vllm.ai/projects/recipes/en/latest/Google/Gemma4.html>
- vLLM OpenAI-compatible server extra parameters: <https://docs.vllm.ai/en/stable/serving/openai_compatible_server/>
- Google media resolution guide: <https://ai.google.dev/gemini-api/docs/media-resolution>
- vLLM issue on concurrent mixed-resolution Gemma 4 crashes: <https://github.com/vllm-project/vllm/issues/39681>
- vLLM PR speeding up per-request `mm_processor_kwargs`: <https://github.com/vllm-project/vllm/pull/26483>

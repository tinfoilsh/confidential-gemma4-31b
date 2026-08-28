#!/usr/bin/env bash

IMAGE_PATH="test.jpg"
API_KEY="tk_1GbIVVi50KuUjG2aAYrkOUytEq7vEWMmi1mmrrUGou7q3Ufy"
MIME=$(file -b --mime-type "$IMAGE_PATH")
IMG_B64=$(base64 < "$IMAGE_PATH" | tr -d '\n')

curl -sS https://inference.tinfoil.sh/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d @- <<JSON
{
  "model": "gemma4-31b",
  "messages": [{
    "role": "user",
    "content": [
      {"type": "image_url", "image_url": {"url": "data:$MIME;base64,$IMG_B64"}},
      {"type": "text", "text": "Locate the handwritten lines and return bounding boxes."}
    ]
  }],
  "max_tokens": 1024,
  "temperature": 0,
  "mm_processor_kwargs": {"max_soft_tokens": 1120}
}
JSON

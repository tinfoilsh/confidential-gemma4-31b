#!/usr/bin/env bash
set -euo pipefail

API_KEY="${TINFOIL_API_KEY:-tk_1GbIVVi50KuUjG2aAYrkOUytEq7vEWMmi1mmrrUGou7q3Ufy}"
MODEL="${MODEL:-gemma4-31b}"
IMAGE_URL="${1:-https://tile.loc.gov/storage-services/service/pnp/ppmsca/86400/86484v.jpg}"
PROMPT="${2:-Transcribe the first 12 handwritten lines exactly as they appear. Output plain text only.}"
BUDGET="${BUDGET:-560}"
MAX_TOKENS="${MAX_TOKENS:-500}"

json_string() {
  python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1"
}

PROMPT_JSON="$(json_string "$PROMPT")"

IMG_B64="$(curl -fsSL -A "Mozilla/5.0" "$IMAGE_URL" | base64 | tr -d '\n')"

if [[ "$BUDGET" == "default" || -z "$BUDGET" ]]; then
  MM_JSON=""
else
  MM_JSON=", \"mm_processor_kwargs\": {\"max_soft_tokens\": $BUDGET}"
fi

curl -sS https://inference.tinfoil.sh/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d @- <<JSON
{
  "model": "$MODEL",
  "messages": [{
    "role": "user",
    "content": [
      {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,$IMG_B64"}},
      {"type": "text", "text": $PROMPT_JSON}
    ]
  }],
  "max_tokens": $MAX_TOKENS,
  "temperature": 0
  $MM_JSON
}
JSON

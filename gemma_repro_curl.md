# Gemma 4 Curl Repro

Use `curl` to fetch the image client-side, base64 it locally, and send a `data:` URL to Tinfoil. This avoids backend image-fetch failures and is the path we verified against the live endpoint.

## Test Image

Real handwritten page:

- Library of Congress item page: <https://www.loc.gov/pictures/item/2023637795/>
- Direct JPEG: <https://tile.loc.gov/storage-services/service/pnp/ppmsca/86400/86484v.jpg>

## Single Request

```bash
IMG_URL="https://tile.loc.gov/storage-services/service/pnp/ppmsca/86400/86484v.jpg"
API_KEY="tk_..."

IMG_B64=$(curl -fsSL -A "Mozilla/5.0" "$IMG_URL" | base64 | tr -d '\n')

curl -sS https://inference.tinfoil.sh/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d @- <<JSON
{
  "model": "gemma4-31b",
  "messages": [{
    "role": "user",
    "content": [
      {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,$IMG_B64"}},
      {"type": "text", "text": "Transcribe the first 12 handwritten lines exactly as they appear. Output plain text only."}
    ]
  }],
  "max_tokens": 500,
  "temperature": 0,
  "mm_processor_kwargs": {"max_soft_tokens": 560}
}
JSON
```

## Compare Budgets

```bash
IMG_URL="https://tile.loc.gov/storage-services/service/pnp/ppmsca/86400/86484v.jpg"
API_KEY="tk_..."
IMG_B64=$(curl -fsSL -A "Mozilla/5.0" "$IMG_URL" | base64 | tr -d '\n')

for BUDGET in default 280 560 1120; do
  if [ "$BUDGET" = "default" ]; then
    MM=""
  else
    MM=", \"mm_processor_kwargs\": {\"max_soft_tokens\": $BUDGET}"
  fi

  echo "=== $BUDGET ==="
  curl -sS https://inference.tinfoil.sh/v1/chat/completions \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $API_KEY" \
    -d @- <<JSON
{
  "model": "gemma4-31b",
  "messages": [{
    "role": "user",
    "content": [
      {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,$IMG_B64"}},
      {"type": "text", "text": "Reply with the single word OK."}
    ]
  }],
  "max_tokens": 8,
  "temperature": 0
  $MM
}
JSON
  echo
done
```

Expected behavior:

- `default` and explicit `280` should have the same prompt token count
- `560` and `1120` should have higher prompt token counts
- on OCR/transcription prompts, the output should visibly change as the budget increases

## Notes

- The client-side fetch matters. Do not ask the backend to fetch the image URL directly for this repro.
- The `Mozilla/5.0` user-agent matters for the Library of Congress image URL.
- This is enough to verify that `mm_processor_kwargs.max_soft_tokens` works client-side on the Tinfoil deployment.

#!/usr/bin/env python3

import base64
import os
import sys
import urllib.request
from pathlib import Path

from tinfoil import TinfoilAI


args = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
IMAGE = args[0] if args else "https://tile.loc.gov/storage-services/service/pnp/ppmsca/86400/86484v.jpg"
PROMPT = args[1] if len(args) > 1 else "Transcribe the handwriting. Output plain text only."
MODEL = os.getenv("MODEL", "gemma4-31b")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1024"))
CASES = [("default", None), ("280", 280), ("560", 560), ("1120", 1120)]

def sniff_image_mime(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return None

def to_data_url(src: str) -> str:
    if src.startswith(("http://", "https://")):
        req = urllib.request.Request(
            src,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "image/*,*/*;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
            header_mime = resp.headers.get_content_type()
        sniffed_mime = sniff_image_mime(data)
        if sniffed_mime is None:
            preview = data[:120].decode("utf-8", errors="replace")
            raise ValueError(
                f"URL did not return decodable image bytes. "
                f"content_type={header_mime!r} preview={preview!r}"
            )
        mime = sniffed_mime
    else:
        path = Path(src)
        if not path.is_file():
            raise FileNotFoundError(f"Image not found: {path}")
        data = path.read_bytes()
        mime = sniff_image_mime(data)
        if mime is None:
            raise ValueError(f"Local file is not a supported image: {path}")
    return f"data:{mime};base64," + base64.b64encode(data).decode()

image_url = to_data_url(IMAGE)

client = TinfoilAI(
    api_key=os.environ["TINFOIL_API_KEY"])

messages = [{
    "role": "user",
    "content": [
        {"type": "image_url", "image_url": {"url": image_url}},
        {"type": "text", "text": PROMPT},
    ],
}]

for label, budget in CASES:
    extra_body = None if budget is None else {
        "mm_processor_kwargs": {"max_soft_tokens": budget}
    }
    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=MAX_TOKENS,
        temperature=0,
        extra_body=extra_body,
    )
    print(f"=== {label} ===")
    print("prompt_tokens:", resp.usage.prompt_tokens)
    print(resp.choices[0].message.content[:2000])
    print()

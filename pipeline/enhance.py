"""
AI photoreal polish — image-to-image enhancement of a finished VTK render.

Feeds the render BACK to an image model as a structural reference so the building
geometry, camera and materials are preserved, and the model only adds realism
(lighting, sky, material grain, context). This is the on-mission use of AI: it
enhances YOUR massing, it does not invent a new building (text-to-image is off).

Provider: Google Gemini image models ("nano banana" family) via google-genai.
Falls back across model names. Raises on failure so callers can keep the
original render.
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image

DEFAULT_PROMPT = (
    "Enhance this architectural massing render into a photorealistic image. "
    "Keep the EXACT same building geometry, camera angle, proportions, massing "
    "and materials — do not add, remove, move or reshape anything. Preserve the "
    "brick facade, the metal balcony rails, the recessed window openings and the "
    "roof. Improve only the realism: natural daylight, soft accurate shadows, a "
    "clean sky, true material colour and grain, subtle ambient occlusion, crisp "
    "professional architectural photography. No text, no labels, no people, no "
    "extra buildings."
)

MODELS = [
    "gemini-2.5-flash-image",
    "gemini-3-pro-image",
    "gemini-3.1-flash-image",
    "gemini-2.0-flash-preview-image-generation",
]


def _payload(in_path: Path, max_px: int = 1280) -> bytes:
    """Downscale the reference to max_px on the long side (saves cost/quota; the
    model only needs structure, not full resolution)."""
    import io
    im = Image.open(in_path).convert("RGB")
    if max(im.size) > max_px:
        s = max_px / max(im.size)
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, "PNG")
    return buf.getvalue()


def enhance_image(in_path: str | Path, out_path: str | Path,
                  prompt: str = DEFAULT_PROMPT, api_key: str | None = None,
                  model: str | None = None, max_px: int = 1280) -> str:
    """Image-to-image enhance `in_path` -> `out_path`. Returns out_path.

    Raises QuotaError on 429 (free tier / quota) so callers can guide the user.
    """
    from google import genai
    from google.genai import types

    in_path, out_path = Path(in_path), Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    api_key = api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

    client = genai.Client(api_key=api_key)
    contents = [prompt, types.Part.from_bytes(
        data=_payload(in_path, max_px), mime_type="image/png")]
    config = types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"])

    tries = [m for m in ([model, os.getenv("GEMINI_MODEL"), *MODELS]) if m]
    last = None
    quota_hit = False
    for m in dict.fromkeys(tries):
        try:
            resp = client.models.generate_content(model=m, contents=contents, config=config)
            for part in resp.candidates[0].content.parts:
                inline = getattr(part, "inline_data", None)
                if inline and inline.data:
                    out_path.write_bytes(inline.data)
                    with Image.open(out_path) as im:
                        im.convert("RGB").save(out_path, "PNG")
                    print(f"   [enhance] model: {m}")
                    return str(out_path)
            last = RuntimeError(f"{m}: no image in response")
        except Exception as exc:
            last = exc
            if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                quota_hit = True
    if quota_hit:
        raise QuotaError(
            "Gemini image quota exhausted (429). The free tier does not grant "
            "image-generation quota - enable billing on the API key "
            "(https://ai.google.dev -> billing) and retry. Cost ~ $0.04/image.")
    raise RuntimeError(f"enhance failed: {last}")


class QuotaError(RuntimeError):
    """Raised when the provider rejects the request for quota/billing reasons."""


# ── OpenAI backend (gpt-image-1, image edit) ─────────────────────────────────

def enhance_image_openai(in_path: str | Path, out_path: str | Path,
                         prompt: str = DEFAULT_PROMPT, api_key: str | None = None,
                         model: str = "gpt-image-1", size: str = "1024x1536") -> str:
    """Image-to-image enhance via OpenAI's image edit endpoint.

    Needs `pip install openai`, OPENAI_API_KEY, and billing enabled. gpt-image-1
    takes the render as the input image and repaints it from the prompt while
    keeping the composition. Raises QuotaError on quota/billing rejection.
    """
    import base64

    from openai import OpenAI

    in_path, out_path = Path(in_path), Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    client = OpenAI(api_key=api_key)
    try:
        with open(_downscaled_tmp(in_path), "rb") as fh:
            res = client.images.edit(model=model, image=fh, prompt=prompt, size=size)
    except Exception as exc:
        if "429" in str(exc) or "insufficient_quota" in str(exc) or "billing" in str(exc).lower():
            raise QuotaError(
                "OpenAI image quota/billing error. Add credit / enable billing "
                "(https://platform.openai.com/account/billing) and retry.")
        raise
    out_path.write_bytes(base64.b64decode(res.data[0].b64_json))
    with Image.open(out_path) as im:
        im.convert("RGB").save(out_path, "PNG")
    print(f"   [enhance] openai model: {model}")
    return str(out_path)


def _downscaled_tmp(in_path: Path, max_px: int = 1280) -> Path:
    """Write a downscaled PNG next to the source for the OpenAI file upload."""
    im = Image.open(in_path).convert("RGB")
    if max(im.size) > max_px:
        s = max_px / max(im.size)
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    tmp = in_path.with_name(in_path.stem + "_tmp_in.png")
    im.save(tmp, "PNG")
    return tmp


def enhance(in_path, out_path, provider: str = "gemini", **kw) -> str:
    """Dispatch to a provider: 'gemini' (default) or 'openai'."""
    if provider == "openai":
        return enhance_image_openai(in_path, out_path, **kw)
    return enhance_image(in_path, out_path, **kw)

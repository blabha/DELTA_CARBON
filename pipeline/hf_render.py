"""
Free(ish) photoreal render via the Hugging Face Inference API (image-to-image).

Takes the VTK massing render as the structural reference and a text prompt, and
asks an image-to-image model to repaint it photorealistically. Requires a free
HF token (https://huggingface.co/settings/tokens) in HF_TOKEN.

Caveats (be realistic): free serverless inference is rate-limited and models
come and go; image-to-image control is weaker than Gemini/SDXL-ControlNet. This
is the "$0, see some AI output" path, not the best-quality path.
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image

# Free serverless text-to-image (works on hf-inference today).
T2I_MODEL = os.getenv("HF_T2I_MODEL", "black-forest-labs/FLUX.1-schnell")
# Image-to-image needs a paid provider; tried first, then we fall back to T2I.
IMG2IMG_MODEL = os.getenv("HF_IMG2IMG_MODEL", "stabilityai/stable-diffusion-xl-refiner-1.0")


def render_with_hf(
    source_path: str | Path,
    prompt: str,
    out_path: str | Path,
    token: str,
    model: str | None = None,
) -> str:
    """Render via HF. Returns the mode used: 'hf-img2img' or 'hf-text2img'.

    Tries image-to-image first (faithful to the massing, needs a paid provider),
    then falls back to free text-to-image (photoreal but a concept, not the exact
    geometry). Raises only if both fail.
    """
    from huggingface_hub import InferenceClient

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    client = InferenceClient(provider="hf-inference", token=token)

    # 1) image-to-image (faithful) — usually unavailable on the free provider.
    try:
        result = client.image_to_image(
            Path(source_path).read_bytes(), prompt=prompt,
            model=model or IMG2IMG_MODEL)
        if isinstance(result, Image.Image):
            result.convert("RGB").save(out_path, "PNG")
            return "hf-img2img"
    except Exception:
        pass

    # 2) free text-to-image (concept, not exact geometry).
    result = client.text_to_image(prompt, model=T2I_MODEL)
    if not isinstance(result, Image.Image):
        raise RuntimeError("HF returned no image")
    result.convert("RGB").save(out_path, "PNG")
    return "hf-text2img"

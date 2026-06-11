"""
Step 5 — Visualisation using the Gemini API.

Given the textured massing composite + the material specs, ask Gemini to produce
a photorealistic architectural render (image-to-image). When no GEMINI_API_KEY
is configured (or the SDK / call fails), fall back to an offline MOCK render so
the pipeline always produces an output — mirroring Stage 3's offline mode.
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .models import RenderResult

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-preview-image-generation")


def render_visualisation(
    composite_path: str | Path,
    face_specs: list[dict],
    out_path: str | Path,
    project_name: str,
    site_location: str,
    building_type: str,
    api_key: str | None = None,
) -> RenderResult:
    """Render the final visualisation, using Gemini if available else a mock."""
    composite_path = Path(composite_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    prompt = build_prompt(face_specs, project_name, site_location, building_type)

    api_key = api_key or os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            _render_with_gemini(composite_path, prompt, out_path, api_key)
            print("   [gemini] render generated via Gemini API")
            return RenderResult(str(out_path), "gemini", prompt, face_specs)
        except Exception as exc:
            print(f"   [gemini] API render failed ({exc}); using mock render")

    _render_mock(composite_path, face_specs, project_name, site_location, out_path)
    return RenderResult(str(out_path), "mock", prompt, face_specs)


def build_prompt(face_specs, project_name, site_location, building_type) -> str:
    lines = [
        "Photorealistic architectural visualisation of a "
        f"{building_type.lower()} building in {site_location}.",
        "Use the provided massing image as the exact geometry and camera angle.",
        "Apply these materials to the building surfaces:",
    ]
    for fs in face_specs:
        lines.append(
            f"  - {fs['surface_type']}: {fs['product_name']} "
            f"({fs['material_category']}, {fs['manufacturer']})"
        )
    lines += [
        "Natural daylight, soft shadows, clear sky, professional architectural "
        "photography, high detail, true material colours and grain.",
    ]
    return "\n".join(lines)


# ── Gemini integration ──────────────────────────────────────────────────────

def _render_with_gemini(composite_path: Path, prompt: str, out_path: Path, api_key: str):
    """Image-to-image render via the Gemini API. Raises on any failure."""
    from google import genai            # google-genai SDK
    from google.genai import types

    client = genai.Client(api_key=api_key)
    img_bytes = Path(composite_path).read_bytes()
    contents = [prompt, types.Part.from_bytes(data=img_bytes, mime_type="image/png")]
    config = types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"])

    # Try the configured model first, then known image-generation model names.
    models = [m for m in (
        os.getenv("GEMINI_MODEL"),
        "gemini-3-pro-image",
        "gemini-3.1-flash-image",
        "gemini-2.5-flash-image",
    ) if m]

    last_err = None
    for model in dict.fromkeys(models):     # de-dupe, keep order
        try:
            response = client.models.generate_content(
                model=model, contents=contents, config=config)
            for part in response.candidates[0].content.parts:
                inline = getattr(part, "inline_data", None)
                if inline and inline.data:
                    out_path.write_bytes(inline.data)
                    with Image.open(out_path) as im:
                        im.convert("RGB").save(out_path, "PNG")
                    print(f"   [gemini] model: {model}")
                    return
            last_err = RuntimeError(f"{model}: no image in response")
        except Exception as exc:
            last_err = exc
            continue
    raise RuntimeError(f"Gemini render failed: {last_err}")


# ── offline mock render ─────────────────────────────────────────────────────

def _render_mock(composite_path, face_specs, project_name, site_location, out_path):
    """Annotate the textured composite as a stand-in for the Gemini render."""
    base = Image.open(composite_path).convert("RGB")
    w, h = base.size
    banner_h = 168
    canvas = Image.new("RGB", (w, h + banner_h), (28, 32, 38))
    canvas.paste(base, (0, 0))
    draw = ImageDraw.Draw(canvas)

    title_font = _font(24)
    body_font = _font(17)
    small_font = _font(15)

    # Left column: project + site.
    draw.text((24, h + 16), f"{project_name}", font=title_font, fill=(240, 240, 240))
    draw.text((24, h + 46), f"{site_location}", font=body_font, fill=(170, 180, 190))

    # Materials list below the title (full width, own rows).
    my = h + 80
    draw.text((24, my), "Materials applied:", font=body_font, fill=(200, 205, 210))
    for i, fs in enumerate(face_specs):
        draw.text(
            (40, my + 22 + i * 20),
            f"• {fs['surface_type']}: {fs['product_name']}  "
            f"({fs['co2e_per_m2']:.1f} kg CO₂e/m²)",
            font=small_font, fill=(225, 225, 225),
        )

    # Right column: mock notice.
    draw.text((w - 230, h + 16), "MOCK RENDER", font=title_font, fill=(255, 170, 90))
    draw.text((w - 230, h + 48), "set GEMINI_API_KEY", font=small_font, fill=(150, 150, 150))
    draw.text((w - 230, h + 66), "for photoreal output", font=small_font, fill=(150, 150, 150))

    canvas.save(out_path, "PNG")


def _font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()

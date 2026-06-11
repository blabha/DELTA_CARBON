"""
Step 3 — Apply texture to the massing model.

The real massing model (OBJ/glTF from Stage 2) is not wired in yet, so this
module renders a lightweight placeholder massing: a simple axonometric box with
three readable faces (roof = top, wall = front + side, floor = ground slab).

Each selected material's texture is perspective-warped onto its face(s) so the
output is a textured massing preview. Swap `build_massing_placeholder` /
`FACES` for a real renderer (trimesh/pyrender) once the mesh is available; the
rest of the pipeline is unaffected.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance

from .models import TexturedSurface

CANVAS = (1024, 720)

# Face quads as (upper-left, lower-left, lower-right, upper-right) in canvas px.
FACES: dict[str, tuple] = {
    "roof_top":   ((495, 165), (330, 250), (650, 250), (815, 165)),
    "wall_front": ((330, 250), (330, 610), (650, 610), (650, 250)),
    "wall_side":  ((650, 250), (650, 610), (815, 525), (815, 165)),
    "floor_base": ((495, 525), (330, 610), (650, 610), (815, 525)),
}

# Per-face shading so the box reads as 3D.
_FACE_BRIGHTNESS = {
    "roof_top": 1.0,
    "wall_front": 0.84,
    "wall_side": 0.62,
    "floor_base": 1.10,
}

# Map a comparative-table surface type to the placeholder face(s) it covers.
_SURFACE_TO_FACES = {
    "roof": ["roof_top"],
    "wall": ["wall_front", "wall_side"],
    "floor": ["floor_base"],
}

_EDGE = (60, 64, 70)


def build_massing_placeholder(out_path: str | Path) -> str:
    """Render the untextured base massing (neutral grey faces)."""
    img = _sky_background()
    draw = ImageDraw.Draw(img)
    neutral = {"roof_top": (205, 205, 205), "wall_front": (175, 175, 175),
               "wall_side": (135, 135, 135), "floor_base": (160, 160, 158)}
    for name, quad in FACES.items():
        draw.polygon(_quad_to_polygon(quad), fill=neutral[name], outline=_EDGE)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    return str(out_path)


def apply_textures(
    textured_surfaces: list[TexturedSurface],
    out_path: str | Path,
) -> tuple[str, list[dict]]:
    """Composite each surface's texture onto its face(s).

    Returns (composite_path, face_specs) where face_specs feeds the render prompt.
    """
    img = _sky_background()
    face_specs: list[dict] = []

    # Build a lookup: surface_type -> TexturedSurface.
    by_type = {ts.material.surface_type.lower(): ts for ts in textured_surfaces}

    for surface_type, face_names in _SURFACE_TO_FACES.items():
        ts = by_type.get(surface_type)
        for face_name in face_names:
            quad = FACES[face_name]
            if ts is None:
                # No material for this surface — leave a neutral face.
                ImageDraw.Draw(img).polygon(
                    _quad_to_polygon(quad), fill=(180, 180, 178), outline=_EDGE)
                continue
            texture = Image.open(ts.texture.image_path).convert("RGBA")
            warped = _warp_texture_to_quad(texture, quad, _FACE_BRIGHTNESS[face_name])
            img = Image.alpha_composite(img.convert("RGBA"), warped).convert("RGB")

        if ts is not None:
            face_specs.append({
                "surface_type": ts.material.surface_type,
                "faces": face_names,
                "material_category": ts.material.material_category,
                "product_name": ts.material.product_name,
                "manufacturer": ts.material.manufacturer,
                "co2e_per_m2": ts.material.co2e_per_m2,
                "texture_source": ts.texture.source,
            })

    # Crisp edges on top.
    draw = ImageDraw.Draw(img)
    for quad in FACES.values():
        draw.polygon(_quad_to_polygon(quad), outline=_EDGE)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    return str(out_path), face_specs


# ── helpers ─────────────────────────────────────────────────────────────────

def _sky_background() -> Image.Image:
    """Soft vertical gradient background."""
    w, h = CANVAS
    bg = Image.new("RGB", CANVAS, (235, 238, 242))
    top, bottom = (225, 232, 240), (245, 244, 240)
    for y in range(h):
        t = y / h
        col = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        ImageDraw.Draw(bg).line([(0, y), (w, y)], fill=col)
    return bg


def _quad_to_polygon(quad):
    # quad order is UL, LL, LR, UR -> polygon in drawing order.
    ul, ll, lr, ur = quad
    return [ul, ur, lr, ll]


def _warp_texture_to_quad(texture: Image.Image, quad, brightness: float) -> Image.Image:
    """Perspective-warp a square texture into `quad` on a full-canvas RGBA layer."""
    tw, th = texture.size
    # source corners in same UL, LL, LR, UR order as the destination quad.
    src = [(0, 0), (0, th), (tw, th), (tw, 0)]
    dst = list(quad)
    coeffs = _find_coeffs(dst, src)

    if brightness != 1.0:
        rgb = ImageEnhance.Brightness(texture.convert("RGB")).enhance(brightness)
        texture = Image.merge("RGBA", (*rgb.split(), texture.split()[3]))

    warped = texture.transform(
        CANVAS, Image.PERSPECTIVE, coeffs,
        resample=Image.BICUBIC, fillcolor=(0, 0, 0, 0),
    )
    return warped


def _find_coeffs(dst_corners, src_corners):
    """8 perspective coefficients mapping output(dst) -> input(src) for PIL."""
    matrix = []
    for d, s in zip(dst_corners, src_corners):
        matrix.append([d[0], d[1], 1, 0, 0, 0, -s[0] * d[0], -s[0] * d[1]])
        matrix.append([0, 0, 0, d[0], d[1], 1, -s[1] * d[0], -s[1] * d[1]])
    A = np.array(matrix, dtype=float)
    B = np.array(src_corners, dtype=float).reshape(8)
    res = np.linalg.solve(A, B)
    return res.tolist()

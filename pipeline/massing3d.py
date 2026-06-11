"""
Offline 3D massing render (no Gemini key required).

Renders a real 3D box (true geometry, camera angle, depth shading) with each
material's texture mapped onto its faces, using matplotlib's 3D engine — fully
software, headless, deterministic. This is a stand-in for the Gemini photoreal
render and for the real Stage-2 mesh: swap the box dimensions / face mapping for
a loaded OBJ when that's available.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from .models import TexturedSurface

# Box dimensions (metres-ish, purely for proportion): width X, depth Y, height Z.
_W, _D, _H = 10.0, 8.0, 9.0
_GRID = 48  # texture sampling resolution per face

# Per-face brightness so the massing reads as 3D (shade=False, so we bake it).
_FACE_SHADE = {
    "roof": 1.00,
    "wall_front": 0.88,
    "wall_right": 0.66,
    "wall_back": 0.72,
    "wall_left": 0.60,
    "floor": 1.08,
}

# Which placeholder faces each comparative-table surface type covers.
_SURFACE_TO_FACES = {
    "roof": ["roof"],
    "wall": ["wall_front", "wall_right", "wall_back", "wall_left"],
    "floor": ["floor"],
}

_NEUTRAL = (0.72, 0.72, 0.72)


def render_massing_3d(
    textured_surfaces: list[TexturedSurface],
    out_path: str | Path,
    project_name: str = "",
    site_location: str = "",
    elev: float = 22.0,
    azim: float = -54.0,
) -> str:
    """Render the textured massing as a 3D image."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Resolve a texture array per face.
    tex_by_type = {ts.material.surface_type.lower(): ts for ts in textured_surfaces}
    face_textures: dict[str, np.ndarray] = {}
    legend: list[tuple[str, str]] = []
    for surface_type, faces in _SURFACE_TO_FACES.items():
        ts = tex_by_type.get(surface_type)
        arr = _load_texture_array(ts.texture.image_path) if ts else None
        for face in faces:
            face_textures[face] = _shade(arr, _FACE_SHADE[face])
        if ts:
            legend.append((ts.material.surface_type, ts.material.product_name))

    fig = plt.figure(figsize=(9, 7.2), dpi=120)
    ax = fig.add_subplot(111, projection="3d")
    ax.set_proj_type("persp")

    for face, colors in face_textures.items():
        X, Y, Z = _face_grid(face)
        ax.plot_surface(
            X, Y, Z, facecolors=colors, rstride=1, cstride=1,
            shade=False, antialiased=False, linewidth=0,
        )

    _style_axes(ax, elev, azim)
    _add_titles(fig, project_name, site_location, legend)

    fig.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return str(out_path)


# ── geometry ────────────────────────────────────────────────────────────────

def _face_grid(face: str):
    n = _GRID
    a = np.linspace(0, 1, n)
    u, v = np.meshgrid(a, a)
    if face == "roof":
        return u * _W, v * _D, np.full_like(u, _H)
    if face == "floor":
        return u * _W, v * _D, np.zeros_like(u)
    if face == "wall_front":   # y = 0
        return u * _W, np.zeros_like(u), v * _H
    if face == "wall_back":    # y = D
        return u * _W, np.full_like(u, _D), v * _H
    if face == "wall_left":    # x = 0
        return np.zeros_like(u), u * _D, v * _H
    if face == "wall_right":   # x = W
        return np.full_like(u, _W), u * _D, v * _H
    raise ValueError(face)


# ── texture helpers ─────────────────────────────────────────────────────────

def _load_texture_array(path: str) -> np.ndarray:
    img = Image.open(path).convert("RGB").resize((_GRID, _GRID), Image.BILINEAR)
    return np.asarray(img, dtype=float) / 255.0


def _shade(arr: np.ndarray | None, factor: float) -> np.ndarray:
    n = _GRID
    if arr is None:
        rgb = np.ones((n, n, 3)) * np.array(_NEUTRAL)
    else:
        rgb = np.clip(arr * factor, 0, 1)
    rgba = np.concatenate([rgb, np.ones((n, n, 1))], axis=2)
    return rgba


# ── presentation ────────────────────────────────────────────────────────────

def _style_axes(ax, elev, azim):
    ax.view_init(elev=elev, azim=azim)
    try:
        ax.set_box_aspect((_W, _D, _H))
    except Exception:
        pass
    ax.set_xlim(0, _W)
    ax.set_ylim(0, _D)
    ax.set_zlim(0, _H)
    ax.set_axis_off()
    for pane in (ax.xaxis, ax.yaxis, ax.zaxis):
        pane.pane.set_visible(False)


def _add_titles(fig, project_name, site_location, legend):
    if project_name:
        fig.text(0.5, 0.965, project_name, ha="center", va="top",
                 fontsize=15, fontweight="bold", color="#1a3a5c")
    if site_location:
        fig.text(0.5, 0.935, site_location, ha="center", va="top",
                 fontsize=10, color="#2a7d6f")
    if legend:
        line = "   ".join(f"{t}: {p}" for t, p in legend)
        fig.text(0.5, 0.03, line, ha="center", va="bottom",
                 fontsize=8, color="#444444")

"""
Interactive 3D massing export (offline, no Gemini).

Builds a real textured 3D model of the massing (roof / walls / floor each with
its own material texture) and exports:

  - massing.glb  — a standard glTF binary you can open in any 3D viewer
                   (Windows 3D Viewer, the VS Code glTF extension, Blender, …)
  - massing_viewer.html — a self-contained page (texture embedded as base64)
                   that you double-click to orbit / pan / zoom with the mouse.

Swap the box geometry for a loaded Stage-2 OBJ when available — the texturing
and export logic are unchanged.
"""

from __future__ import annotations

import base64
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image

from .models import TexturedSurface

# Box dimensions (proportions only): width X, depth Y, height Z.
_W, _D, _H = 10.0, 8.0, 9.0

# Corner indices for a box centred at the origin.
def _corners():
    cx, cy, cz = _W / 2, _D / 2, _H / 2
    return {
        0: (-cx, -cy, -cz), 1: (cx, -cy, -cz), 2: (cx, cy, -cz), 3: (-cx, cy, -cz),
        4: (-cx, -cy, cz), 5: (cx, -cy, cz), 6: (cx, cy, cz), 7: (-cx, cy, cz),
    }

# Quads (ordered for outward-facing normals) per surface group.
_FACE_QUADS = {
    "roof":  [(4, 5, 6, 7)],
    "floor": [(0, 3, 2, 1)],
    "wall":  [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)],
}

_NEUTRAL = {"roof": (200, 200, 200), "wall": (175, 175, 175), "floor": (160, 160, 158)}


def build_glb(textured_surfaces: list[TexturedSurface], out_glb: str | Path) -> str:
    """Build the textured box scene and export a GLB."""
    out_glb = Path(out_glb)
    out_glb.parent.mkdir(parents=True, exist_ok=True)

    tex_by_type = {ts.material.surface_type.lower(): ts for ts in textured_surfaces}
    corners = _corners()

    scene = trimesh.Scene()
    for group, quads in _FACE_QUADS.items():
        ts = tex_by_type.get(group)
        image = _texture_image(ts, group)
        mesh = _quad_mesh(quads, corners, image)
        scene.add_geometry(mesh, geom_name=group)

    glb_bytes = scene.export(file_type="glb")
    out_glb.write_bytes(glb_bytes)
    return str(out_glb)


def build_viewer_html(glb_path: str | Path, out_html: str | Path,
                      title: str = "SURROUND Massing", subtitle: str = "") -> str:
    """Write a self-contained HTML viewer with the GLB embedded as base64."""
    glb_path = Path(glb_path)
    out_html = Path(out_html)
    b64 = base64.b64encode(glb_path.read_bytes()).decode("ascii")
    data_uri = f"data:model/gltf-binary;base64,{b64}"

    html = _HTML_TEMPLATE.format(title=title, subtitle=subtitle, data_uri=data_uri)
    out_html.write_text(html, encoding="utf-8")
    return str(out_html)


# ── mesh construction ───────────────────────────────────────────────────────

def _quad_mesh(quads, corners, image: Image.Image) -> trimesh.Trimesh:
    verts, faces, uv = [], [], []
    for q in quads:
        base = len(verts)
        for idx in q:
            verts.append(corners[idx])
        uv.extend([(0, 0), (1, 0), (1, 1), (0, 1)])
        faces.append((base, base + 1, base + 2))
        faces.append((base, base + 2, base + 3))

    visual = trimesh.visual.TextureVisuals(
        uv=np.array(uv, dtype=float), image=image
    )
    return trimesh.Trimesh(
        vertices=np.array(verts, dtype=float),
        faces=np.array(faces, dtype=np.int64),
        visual=visual, process=False,
    )


def _texture_image(ts: TexturedSurface | None, group: str) -> Image.Image:
    if ts is not None:
        return Image.open(ts.texture.image_path).convert("RGB")
    return Image.new("RGB", (256, 256), _NEUTRAL[group])


# ── viewer template (model-viewer web component) ────────────────────────────

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  html, body {{ margin: 0; height: 100%; background: #eef1f4; font-family: Segoe UI, Arial, sans-serif; }}
  header {{ position: absolute; top: 0; left: 0; right: 0; padding: 14px 20px; z-index: 2; }}
  header h1 {{ margin: 0; font-size: 18px; color: #1a3a5c; }}
  header p {{ margin: 2px 0 0; font-size: 12px; color: #2a7d6f; }}
  model-viewer {{ width: 100vw; height: 100vh; --poster-color: transparent; }}
  .hint {{ position: absolute; bottom: 12px; left: 0; right: 0; text-align: center;
           font-size: 12px; color: #555; z-index: 2; }}
</style>
<script type="module"
  src="https://ajax.googleapis.com/ajax/libs/model-viewer/3.5.0/model-viewer.min.js"></script>
</head>
<body>
  <header>
    <h1>{title}</h1>
    <p>{subtitle}</p>
  </header>
  <model-viewer
    src="{data_uri}"
    alt="SURROUND building massing"
    camera-controls
    enable-pan
    touch-action="none"
    shadow-intensity="1"
    exposure="1.0"
    camera-orbit="-50deg 70deg auto"
    interaction-prompt="none">
  </model-viewer>
  <div class="hint">Drag to orbit &middot; Scroll to zoom &middot; Right-drag (or two-finger) to pan</div>
</body>
</html>
"""

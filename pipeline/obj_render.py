"""
Render a classified massing mesh, and export it for interactive viewing.

  - render_source_image: a shaded, material-coloured view of the building
    (matplotlib 3D, headless). This is the source image for the Gemini step
    and the offline stand-in for the photoreal render.
  - export_glb: the textured/coloured model as GLB + a web viewer so the
    building can be orbited / panned / zoomed.

Faces are coloured per material group (roof / wall / floor) using a colour
sampled from that material's texture, so the render reflects the real EPD
choices from the comparative table.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection
from PIL import Image

from .interactive3d import build_viewer_html

_LIGHT = np.array([0.4, 0.5, 0.85])
_LIGHT = _LIGHT / np.linalg.norm(_LIGHT)


def material_colour(texture_path: str | None, fallback=(160, 160, 160)) -> np.ndarray:
    """Representative RGB (0–1) for a material, sampled from its texture."""
    if texture_path and Path(texture_path).exists():
        img = Image.open(texture_path).convert("RGB").resize((32, 32))
        return np.asarray(img, dtype=float).reshape(-1, 3).mean(0) / 255.0
    return np.array(fallback, dtype=float) / 255.0


def render_source_image(
    mesh: trimesh.Trimesh,
    face_groups: dict,
    group_colours: dict,
    out_path: str | Path,
    project_name: str = "",
    site_location: str = "",
    elev: float = 18.0,
    azim: float = -62.0,
) -> str:
    """Render a shaded, material-coloured image of the massing."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    tris = mesh.vertices[mesh.faces]               # (F, 3, 3)
    normals = mesh.face_normals
    facecolours = np.ones((len(mesh.faces), 4))

    for group, idx in face_groups.items():
        if len(idx) == 0:
            continue
        base = group_colours.get(group, np.array([0.7, 0.7, 0.7]))
        shade = 0.35 + 0.65 * np.clip(normals[idx] @ _LIGHT, 0, 1)   # (n,)
        facecolours[idx, :3] = np.clip(base[None, :] * shade[:, None], 0, 1)

    fig = plt.figure(figsize=(10, 7.5), dpi=120)
    ax = fig.add_subplot(111, projection="3d")
    ax.set_proj_type("persp")

    # Ground plane for grounding the building.
    _add_ground(ax, mesh.bounds)

    coll = Poly3DCollection(tris, facecolors=facecolours, edgecolors=None, linewidths=0)
    ax.add_collection3d(coll)

    # Draw only real geometric edges (sharp corners), not triangulation diagonals.
    if len(mesh.faces) <= 2000:
        _add_sharp_edges(ax, mesh)

    _frame_axes(ax, mesh.bounds, elev, azim)
    _titles(fig, project_name, site_location, group_colours)

    fig.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return str(out_path)


def export_glb(
    mesh: trimesh.Trimesh,
    face_groups: dict,
    group_colours: dict,
    out_glb: str | Path,
    out_html: str | Path | None = None,
    project_name: str = "",
    site_location: str = "",
) -> tuple[str, str | None]:
    """Export the coloured massing as GLB (+ optional web viewer)."""
    out_glb = Path(out_glb)
    out_glb.parent.mkdir(parents=True, exist_ok=True)

    face_colours = np.full((len(mesh.faces), 4), 200, dtype=np.uint8)
    for group, idx in face_groups.items():
        if len(idx) == 0:
            continue
        rgb = (np.clip(group_colours.get(group, np.array([0.7, 0.7, 0.7])), 0, 1) * 255).astype(np.uint8)
        face_colours[idx, :3] = rgb

    coloured = mesh.copy()
    coloured.visual = trimesh.visual.ColorVisuals(coloured, face_colors=face_colours)
    scene = trimesh.Scene(coloured)
    out_glb.write_bytes(scene.export(file_type="glb"))

    html_path = None
    if out_html is not None:
        html_path = build_viewer_html(out_glb, out_html, title=project_name, subtitle=site_location)
    return str(out_glb), html_path


def export_textured_glb(
    mesh: trimesh.Trimesh,
    face_groups: dict,
    group_textures: dict,
    out_glb: str | Path,
    out_html: str | Path | None = None,
    project_name: str = "",
    site_location: str = "",
    tile: float = 4.0,
) -> tuple[str, str | None]:
    """Export the massing with real image textures (box-projected UVs) per group."""
    out_glb = Path(out_glb)
    out_glb.parent.mkdir(parents=True, exist_ok=True)

    scene = trimesh.Scene()
    for group, sub, _img in build_textured_submeshes(mesh, face_groups, group_textures, tile):
        scene.add_geometry(sub, geom_name=group)

    out_glb.write_bytes(scene.export(file_type="glb"))
    html_path = None
    if out_html is not None:
        html_path = build_viewer_html(out_glb, out_html, title=project_name, subtitle=site_location)
    return str(out_glb), html_path


def build_textured_submeshes(mesh, face_groups, group_textures, tile: float = 4.0):
    """Return [(group, submesh_with_uv, texture_image), ...] for each non-empty group."""
    out = []
    for group, idx in face_groups.items():
        if len(idx) == 0:
            continue
        image = group_textures.get(group)
        if image is None:
            continue
        out.append((group, _textured_submesh(mesh, idx, image, tile), image))
    return out


def _textured_submesh(mesh, face_idx, image: Image.Image, tile: float) -> trimesh.Trimesh:
    """Build a submesh with per-face vertices and box-projected (tiling) UVs.

    Fully vectorised so it scales to millions of faces.
    """
    face_idx = np.asarray(face_idx, dtype=np.int64)
    tris = mesh.vertices[mesh.faces[face_idx]]          # (F, 3, 3)
    nrm = mesh.face_normals[face_idx]                   # (F, 3)
    dom = np.argmax(np.abs(nrm), axis=1)                # dominant axis per face
    u_ax = np.where(dom == 0, 1, 0)                     # x-faces use y, else x
    v_ax = np.where(dom == 2, 1, 2)                     # z-faces use y, else z

    F = len(face_idx)
    fi = np.arange(F)[:, None]
    tri_i = np.arange(3)[None, :]
    u = tris[fi, tri_i, u_ax[:, None]]                  # (F, 3)
    v = tris[fi, tri_i, v_ax[:, None]]                  # (F, 3)
    uv = np.stack([u, v], axis=-1).reshape(-1, 2) / tile

    verts = tris.reshape(-1, 3)
    faces = np.arange(3 * F, dtype=np.int64).reshape(F, 3)
    visual = trimesh.visual.TextureVisuals(uv=uv, image=image)
    return trimesh.Trimesh(vertices=verts, faces=faces, visual=visual, process=False)


# ── presentation helpers ────────────────────────────────────────────────────

def _add_sharp_edges(ax, mesh, angle_deg=25.0):
    """Overlay only edges where adjacent faces meet at a real corner."""
    try:
        angles = mesh.face_adjacency_angles
        sharp = mesh.face_adjacency_edges[angles > np.radians(angle_deg)]
    except Exception:
        return
    if len(sharp) == 0:
        return
    segments = mesh.vertices[sharp]                 # (M, 2, 3)
    ax.add_collection3d(Line3DCollection(
        segments, colors="#2c3036", linewidths=0.8))


def _add_ground(ax, bounds):
    (x0, y0, z0), (x1, y1, z1) = bounds
    mx, my = (x1 - x0) * 0.6, (y1 - y0) * 0.6
    ground = np.array([
        [x0 - mx, y0 - my, z0], [x1 + mx, y0 - my, z0],
        [x1 + mx, y1 + my, z0], [x0 - mx, y1 + my, z0],
    ])
    ax.add_collection3d(Poly3DCollection(
        [ground], facecolors="#e9ebee", edgecolors=None, zsort="min"))


def _frame_axes(ax, bounds, elev, azim):
    (x0, y0, z0), (x1, y1, z1) = bounds
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_zlim(z0, z1)
    try:
        ax.set_box_aspect((x1 - x0, y1 - y0, z1 - z0))
    except Exception:
        pass
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.pane.set_visible(False)


def _titles(fig, project_name, site_location, group_colours):
    if project_name:
        fig.text(0.5, 0.965, project_name, ha="center", va="top",
                 fontsize=15, fontweight="bold", color="#1a3a5c")
    if site_location:
        fig.text(0.5, 0.935, site_location, ha="center", va="top",
                 fontsize=10, color="#2a7d6f")

"""
Load a massing OBJ and classify each face as glass / roof / wall / floor.

Classification:
  1. Glass — faces whose OBJ material name looks like glass/glazing/window
     (e.g. the Engel House's "Translucent_Glass_Gray"). Parsed directly from the
     OBJ so windows render as glass, not wall.
  2. Otherwise roof/wall/floor by group/material keyword, then by face normal
     (up -> roof, down -> floor, side -> wall).

Works on any mesh; the placeholder/generated massing (no glass material) simply
yields no glass group.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh
import trimesh.transformations as tf

_ROOF_KW = ("roof", "canopy")
_FLOOR_KW = ("floor", "slab", "deck", "base", "ground")
_WALL_KW = ("wall", "facade", "envelope", "curtain", "cladding")
_GLASS_KW = ("glass", "glazing", "window", "translucent", "transparent")

_VERTICAL_CUTOFF = 0.45


def load_massing(path: str | Path, up_axis: str | None = None):
    """Return (combined_mesh, {"glass"?, "roof", "wall", "floor": idx[]}).

    The mesh is auto-oriented to Z-up (OBJ is often Y-up). Pass up_axis="x"/"y"/"z"
    to force the source up-axis instead of auto-detecting.
    """
    path = Path(path)
    if path.suffix.lower() == ".obj":
        mesh, face_materials = _parse_obj(path)
    else:
        loaded = trimesh.load(str(path), process=False)
        if isinstance(loaded, trimesh.Scene):
            loaded = loaded.dump(concatenate=True)
        mesh = loaded
        face_materials = [""] * len(mesh.faces)

    orient_to_z_up(mesh, up_axis)
    return mesh, _classify_faces(mesh, face_materials)


def detect_up_axis(mesh: trimesh.Trimesh) -> int:
    """Guess the up-axis (0/1/2) by finding the flat base sitting on the ground."""
    cent = mesh.triangles.mean(axis=1)
    best, score = 2, -1.0
    for a in range(3):
        c = cent[:, a]
        rng = c.max() - c.min()
        if rng < 1e-9:
            continue
        base = c <= c.min() + 0.08 * rng              # bottom band
        down = mesh.face_normals[:, a] < -0.6          # downward-facing
        footprint = float(np.prod([mesh.extents[i] for i in range(3) if i != a]))
        s = mesh.area_faces[base & down].sum() / (footprint + 1e-9)
        if s > score:
            score, best = s, a
    return best


def orient_to_z_up(mesh: trimesh.Trimesh, up_axis: str | None = None) -> trimesh.Trimesh:
    """Rotate the mesh in place so its up-axis becomes +Z."""
    a = {"x": 0, "y": 1, "z": 2}.get(up_axis) if up_axis else detect_up_axis(mesh)
    if a == 1:                                         # Y-up -> Z-up
        mesh.apply_transform(tf.rotation_matrix(np.pi / 2, [1, 0, 0]))
    elif a == 0:                                       # X-up -> Z-up
        mesh.apply_transform(tf.rotation_matrix(-np.pi / 2, [0, 1, 0]))
    return mesh


def _parse_obj(path: Path):
    """Minimal OBJ parser that keeps each face's active material (usemtl)."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    face_mat: list[str] = []
    current = "default"

    raw = Path(path).read_text(errors="ignore").replace("\\\n", " ")  # join continuations
    if True:
        for line in raw.splitlines():
            if line.startswith("v "):
                p = line.split()
                verts.append((float(p[1]), float(p[2]), float(p[3])))
            elif line.startswith("usemtl"):
                current = line.split(maxsplit=1)[1].strip() if len(line.split()) > 1 else "default"
            elif line.startswith("f "):
                idx = []
                for tok in line.split()[1:]:
                    v = int(tok.split("/")[0])
                    idx.append(v - 1 if v > 0 else len(verts) + v)
                for k in range(1, len(idx) - 1):           # fan triangulate
                    faces.append((idx[0], idx[k], idx[k + 1]))
                    face_mat.append(current)

    mesh = trimesh.Trimesh(vertices=np.array(verts, dtype=float),
                           faces=np.array(faces, dtype=np.int64), process=False)
    return mesh, face_mat


def _classify_faces(mesh: trimesh.Trimesh, face_materials: list[str]) -> dict:
    normals = mesh.face_normals
    glass, roof, wall, floor = [], [], [], []

    for i, mat in enumerate(face_materials):
        m = mat.lower()
        if any(k in m for k in _GLASS_KW):
            glass.append(i)
        elif any(k in m for k in _ROOF_KW):
            roof.append(i)
        elif any(k in m for k in _FLOOR_KW):
            floor.append(i)
        elif any(k in m for k in _WALL_KW):
            wall.append(i)
        else:
            nz = normals[i, 2]
            if nz > _VERTICAL_CUTOFF:
                roof.append(i)
            elif nz < -_VERTICAL_CUTOFF:
                floor.append(i)
            else:
                wall.append(i)

    groups = {
        "roof": np.array(roof, dtype=np.int64),
        "wall": np.array(wall, dtype=np.int64),
        "floor": np.array(floor, dtype=np.int64),
    }
    if glass:
        groups["glass"] = np.array(glass, dtype=np.int64)
    return groups

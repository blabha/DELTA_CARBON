import numpy as np
from typing import Dict
from massing_model.parser import MeshGroup

# Rhino layer name substrings → surface type (checked uppercase)
_NAME_MAP = {
    "WALL": "wall",
    "FACADE": "wall",
    "ROOF": "roof",
    "FLOOR": "floor",
    "SLAB": "floor",
    "CEILING": "floor",
    "WINDOW": "window",
    "GLASS": "window",
    "GLAZING": "window",
    "RAILING": "railing",
    "BALUSTRADE": "railing",
    "FRAME": "frame",
    "COLUMN": "column",
    "BEAM": "beam",
}

_UP = np.array([0.0, 0.0, 1.0])
_NORMAL_THRESHOLD = 0.9


def _face_normal(verts: np.ndarray, face: tuple) -> np.ndarray:
    a, b, c = verts[face[0]], verts[face[1]], verts[face[2]]
    n = np.cross(b - a, c - a)
    length = np.linalg.norm(n)
    return n / length if length > 1e-10 else np.zeros(3)


def _classify_by_normal(group: MeshGroup) -> str:
    normals = np.array([_face_normal(group.vertices, f) for f in group.faces])
    avg = normals.mean(axis=0)
    length = np.linalg.norm(avg)
    if length < 1e-10:
        return "wall"
    avg /= length
    dot = float(np.dot(avg, _UP))
    if dot > _NORMAL_THRESHOLD:
        return "roof"
    if dot < -_NORMAL_THRESHOLD:
        return "floor"
    return "wall"


def classify_groups(groups: Dict[str, MeshGroup]) -> Dict[str, str]:
    """Map each group name to a surface type. Uses layer name first, normals as fallback."""
    result = {}
    for name, group in groups.items():
        upper = name.upper()
        matched = next((v for k, v in _NAME_MAP.items() if k in upper), None)
        result[name] = matched if matched else _classify_by_normal(group)
    return result

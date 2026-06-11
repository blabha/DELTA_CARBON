import numpy as np
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class MeshGroup:
    name: str
    vertices: np.ndarray          # shape (N, 3), float64, metres
    faces: List[Tuple[int, int, int]]  # triangulated, 0-based local indices


def parse_obj(filepath: str | Path) -> Dict[str, MeshGroup]:
    """
    Parse an OBJ file and return named mesh groups.
    Groups are defined by `g` or `o` directives; faces are triangulated via fan method.
    Vertices are re-indexed locally per group.
    """
    filepath = Path(filepath)
    global_verts: List[List[float]] = []
    groups: Dict[str, List[Tuple[int, int, int]]] = {"default": []}
    current_group = "default"

    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            token = parts[0]

            if token == "v":
                global_verts.append([float(parts[1]), float(parts[2]), float(parts[3])])

            elif token in ("g", "o"):
                name = parts[1] if len(parts) > 1 else "default"
                current_group = name
                if current_group not in groups:
                    groups[current_group] = []

            elif token == "f":
                indices = []
                for p in parts[1:]:
                    vi = int(p.split("/")[0])
                    vi = len(global_verts) + vi if vi < 0 else vi - 1  # to 0-based
                    indices.append(vi)
                # Fan triangulation: works for convex polygons (standard in massing models)
                for i in range(1, len(indices) - 1):
                    groups[current_group].append((indices[0], indices[i], indices[i + 1]))

    global_arr = np.array(global_verts, dtype=np.float64) if global_verts else np.zeros((0, 3))
    result: Dict[str, MeshGroup] = {}

    for name, face_list in groups.items():
        if not face_list:
            continue
        flat = [vi for tri in face_list for vi in tri]
        unique_global = list(dict.fromkeys(flat))
        g2l = {g: l for l, g in enumerate(unique_global)}
        local_verts = global_arr[unique_global]
        local_faces = [(g2l[a], g2l[b], g2l[c]) for a, b, c in face_list]
        result[name] = MeshGroup(name=name, vertices=local_verts, faces=local_faces)

    return result

import numpy as np
from massing_model.parser import MeshGroup

# Surface types where volume = area × assumed thickness (single-skin surfaces in Rhino).
# All other types (railing, window, frame) are modelled as 3D solids → divergence theorem.
THICKNESS_M: dict[str, float] = {
    "wall": 0.2,
    "floor": 0.2,
    "roof": 0.2,
}


def compute_area(group: MeshGroup) -> float:
    """Total surface area in m² (sum of triangle areas via cross product)."""
    total = 0.0
    v = group.vertices
    for a, b, c in group.faces:
        total += np.linalg.norm(np.cross(v[b] - v[a], v[c] - v[a])) * 0.5
    return float(total)


def compute_volume(group: MeshGroup, surface_type: str = "") -> float:
    """
    Volume in m³.
    - wall / floor / roof: area × assumed thickness (single-skin Rhino surfaces).
    - all others (railing, window, frame): divergence theorem on the closed mesh.
    """
    if surface_type in THICKNESS_M:
        return compute_area(group) * THICKNESS_M[surface_type]

    total = 0.0
    v = group.vertices
    for a, b, c in group.faces:
        total += float(np.dot(v[a], np.cross(v[b], v[c])))
    return abs(total) / 6.0

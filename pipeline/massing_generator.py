"""
Generate a clean, solid massing study (no interior geometry).

Produces a single watertight mesh from stacked, setback volumes — the kind of
clean massing Stage 2 (Rashi) will actually output — so texturing, rendering
and face-classification all behave well. Saved as an OBJ that the rest of the
pipeline loads exactly like a real imported model.
"""

from __future__ import annotations

from pathlib import Path

import trimesh


def generate_massing(out_path: str | Path) -> str:
    """Build a podium + mid-block + setback-tower massing and save as OBJ."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # extents (w=x, d=y, h=z), then translate centre.
    podium = trimesh.creation.box(extents=(34, 22, 7))
    podium.apply_translation((0, 0, 3.5))

    mid = trimesh.creation.box(extents=(34, 16, 9))
    mid.apply_translation((0, -3, 11.5))          # sits on podium, front-aligned

    tower = trimesh.creation.box(extents=(18, 16, 10))
    tower.apply_translation((-6, -3, 21))         # setback tower, offset to one side

    massing = trimesh.boolean.union([podium, mid, tower])
    if isinstance(massing, trimesh.Scene):        # some backends return a scene
        massing = massing.dump(concatenate=True)

    # Rest the model on the ground plane (z = 0).
    massing.apply_translation((0, 0, -massing.bounds[0][2]))

    massing.export(out_path)
    return str(out_path)

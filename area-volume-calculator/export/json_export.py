import json
from pathlib import Path
from typing import Dict
from massing_model.parser import MeshGroup
from geometry.calculator import compute_area, compute_volume, THICKNESS_M


def build_report(groups: Dict[str, MeshGroup], surface_types: Dict[str, str]) -> dict:
    surfaces = []
    totals: Dict[str, float] = {}

    for name, group in groups.items():
        stype = surface_types.get(name, "other")
        area = compute_area(group)
        volume = compute_volume(group, surface_type=stype)
        thickness = THICKNESS_M.get(stype)

        entry = {
            "id": name,
            "type": stype,
            "area_m2": round(area, 4),
            "volume_m3": round(volume, 4),
            "face_count": len(group.faces),
            "vertex_count": len(group.vertices),
        }
        if thickness is not None:
            entry["assumed_thickness_m"] = thickness
        surfaces.append(entry)

        area_key = f"{stype}_area_m2"
        vol_key = f"{stype}_volume_m3"
        totals[area_key] = round(totals.get(area_key, 0.0) + area, 4)
        totals[vol_key] = round(totals.get(vol_key, 0.0) + volume, 4)

    return {"surfaces": surfaces, "totals": dict(sorted(totals.items()))}


def export_json(report: dict, output_path: str | Path) -> None:
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

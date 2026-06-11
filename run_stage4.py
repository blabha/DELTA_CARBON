"""
SURROUND — Stage 4 (Rim) end-to-end, built to run INDEPENDENTLY.

Inputs are self-contained so this runs without the other teammates' code:
  - sample_data/comparative_table.csv  (stand-in for Bhavana's Stage 3 output)
  - massing/imported_massing.obj       (stand-in for Rashi's Stage 2 model)

Flow:
  1. Select best material per surface        (from the sample comparative table)
  2. Get a texture per material               (scrape -> procedural fallback)
  3. Load the massing OBJ and classify faces  (groups -> normals) into roof/wall/floor
  4. Render a material-coloured 3D view        (source image for the render step)
  5. Visualisation (Gemini API, primary)       (real render with key; mock offline)
  +  Export an interactive GLB + web viewer     (orbit / pan / zoom)

Usage:
    python run_stage4.py
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

from PIL import Image

from pipeline.massing_generator import generate_massing
from pipeline.massing_loader import load_massing
from pipeline.models import TexturedSurface
from pipeline.obj_render import (
    build_textured_submeshes,
    export_textured_glb,
    material_colour,
    render_source_image,
)
from pipeline.select_materials import load_selected_materials
from pipeline.texture_library import get_environment, get_maps
from pipeline.texture_scraper import get_texture

load_dotenv()

PROJECT_NAME = "SURROUND Massing — Material Study"
SITE_LOCATION = "22@ Poblenou, Barcelona, Spain"
BUILDING_TYPE = "Residential"

HERE = Path(__file__).parent
# Self-contained inputs (decoupled from teammates). Override via .env if wired up.
COMPARATIVE_TABLE = Path(os.getenv("COMPARATIVE_TABLE", str(HERE / "sample_data" / "comparative_table.csv")))
# Default: the Engel House model. Set MASSING_OBJ to use a real Stage-2 model.
MASSING_OBJ = Path(os.getenv("MASSING_OBJ", str(HERE / "massing" / "imported_massing.obj")))
TEXTURE_DIR = HERE / "assets" / "textures"
OUTPUT_DIR = HERE / "output"

# Which comparative-table surface type drives each massing face group.
_GROUP_TO_SURFACE = {"roof": "roof", "wall": "wall", "floor": "floor"}


def run():
    OUTPUT_DIR.mkdir(exist_ok=True)
    if not os.getenv("GEMINI_API_KEY"):
        print("GEMINI_API_KEY not set — final render runs in OFFLINE MODE (mock).\n")

    # Step 1: select best material per surface.
    selected = load_selected_materials(COMPARATIVE_TABLE)
    by_type = {m.surface_type.lower(): m for m in selected}
    print(f"Selected {len(selected)} material(s) from {COMPARATIVE_TABLE.name}.")

    # Step 2: texture + representative colour per material.
    textured: list[TexturedSurface] = []
    group_colours = {}
    group_textures = {}
    for group, surface_type in _GROUP_TO_SURFACE.items():
        mat = by_type.get(surface_type)
        if mat is None:
            continue
        tex = get_texture(mat, TEXTURE_DIR)
        textured.append(TexturedSurface(material=mat, texture=tex))
        group_colours[group] = material_colour(tex.image_path)
        group_textures[group] = Image.open(tex.image_path).convert("RGB")
        print(f"  {group:5} <- {mat.surface_type:6} {mat.product_name}  [{tex.source}]")

    # Step 3: load the massing model (generate a clean one if missing).
    if not MASSING_OBJ.exists():
        print(f"\nGenerating clean massing -> {MASSING_OBJ.name}")
        generate_massing(MASSING_OBJ)
    print(f"Loading massing: {MASSING_OBJ.name}")
    mesh, face_groups = load_massing(MASSING_OBJ)
    print(f"  {len(mesh.faces)} faces  ->  "
          + ", ".join(f"{g}: {len(idx)}" for g, idx in face_groups.items()))

    # PBR material maps (color/normal/orm) + HDR environment for the render.
    group_maps = {}
    for g, st in _GROUP_TO_SURFACE.items():
        mat = by_type.get(st)
        if mat is not None:
            m = get_maps(mat.material_category)
            if m:
                group_maps[g] = m
    env_hdr = get_environment()

    legend = [
        {
            "label": f"{ts.material.surface_type}: {ts.material.product_name}",
            "detail": f"{ts.material.co2e_per_m2:.1f} kg CO2e/m2",
            "color": group_colours[g],
        }
        for g, st in _GROUP_TO_SURFACE.items()
        for ts in textured if ts.material.surface_type.lower() == st
    ]

    # Step 4-5: faithful PBR + IBL render of THE massing (the deliverable).
    final_path = str(OUTPUT_DIR / "massing_render.png")
    glass_mesh = None
    gi = face_groups.get("glass")
    if gi is not None and len(gi):
        glass_mesh = mesh.submesh([gi], append=True)
        print(f"  glass: {len(gi)} faces (windows)")
    try:
        from pipeline.vtk_render import render_pretty
        submeshes = build_textured_submeshes(mesh, face_groups, group_textures)
        render_pretty(
            submeshes, mesh.bounds, final_path, legend=legend,
            group_maps=group_maps, env_hdr=env_hdr, glass_mesh=glass_mesh,
            project_name=PROJECT_NAME, site_location=SITE_LOCATION,
        )
        render_mode = "vtk-pbr"
        print(f"\nFinal render [vtk-pbr] -> {final_path}")
    except Exception as exc:
        print(f"\n[vtk] render failed ({exc}); using matplotlib fallback.")
        render_source_image(
            mesh, face_groups, group_colours, final_path,
            project_name=PROJECT_NAME, site_location=SITE_LOCATION,
        )
        render_mode = "matplotlib"
        print(f"Final render [matplotlib] -> {final_path}")

    face_specs = [
        {
            "surface_type": ts.material.surface_type,
            "material_category": ts.material.material_category,
            "product_name": ts.material.product_name,
            "manufacturer": ts.material.manufacturer,
            "co2e_per_m2": ts.material.co2e_per_m2,
            "texture_source": ts.texture.source,
        }
        for ts in textured
    ]
    result = type("R", (), {"mode": render_mode, "image_path": final_path})()

    # Extra: interactive textured model for inspection.
    glb, html = export_textured_glb(
        mesh, face_groups, group_textures,
        OUTPUT_DIR / "massing.glb", OUTPUT_DIR / "massing_viewer.html",
        project_name=PROJECT_NAME, site_location=SITE_LOCATION,
    )
    print(f"Interactive model -> {glb}")
    print(f"Web viewer        -> {html}")

    # Manifest.
    manifest = {
        "project": PROJECT_NAME,
        "site": SITE_LOCATION,
        "massing_obj": str(MASSING_OBJ),
        "render_mode": result.mode,
        "final_render": result.image_path,
        "glb": glb,
        "faces_by_group": {g: int(len(idx)) for g, idx in face_groups.items()},
        "surfaces": face_specs,
    }
    (OUTPUT_DIR / "stage4_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nDone.")


if __name__ == "__main__":
    run()

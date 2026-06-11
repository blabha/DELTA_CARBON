"""
Surround Stage 4 — Visualisation Pipeline (Rim)
Entry point that wires the visualisation steps into a single run.

Usage:
    python run_visualisation.py

Reads the Material Comparative Table from Stage 3 (Bhavana). By default it looks
for Bhavana's output relative to this folder; override with COMPARATIVE_TABLE in
a .env file. When no GEMINI_API_KEY is set, the final render runs in OFFLINE
MODE (mock render).

Flow (loops per surface, then renders once all materials are applied):
    1. Select best choice      -> select_materials.load_selected_materials
    2. Get material texture     -> texture_scraper.get_texture   (scrape -> fallback)
    3. Apply texture to model   -> apply_texture.apply_textures
    4. (loop over all surfaces)
    5. Visualisation (Gemini)   -> gemini_render.render_visualisation
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

from pipeline.apply_texture import apply_textures, build_massing_placeholder
from pipeline.gemini_render import render_visualisation
from pipeline.models import TexturedSurface
from pipeline.select_materials import load_selected_materials
from pipeline.texture_scraper import get_texture

load_dotenv()

# ── INPUT CONFIGURATION ───────────────────────────────────────────────────────

PROJECT_NAME = "22@ Poblenou Residential Block"
SITE_LOCATION = "22@ Poblenou, Barcelona, Spain"
BUILDING_TYPE = "Residential"

HERE = Path(__file__).parent

# Stage 3 output (Bhavana). Override via COMPARATIVE_TABLE in .env if needed.
DEFAULT_TABLE = (
    HERE.parent
    / "SURROUND_UPFRONT-CARBON-bhavana (1)"
    / "SURROUND_UPFRONT-CARBON-bhavana"
    / "output"
    / "comparative_table.csv"
)
COMPARATIVE_TABLE = Path(os.getenv("COMPARATIVE_TABLE", str(DEFAULT_TABLE)))

TEXTURE_DIR = HERE / "assets" / "textures"
MASSING_DIR = HERE / "massing"
OUTPUT_DIR = HERE / "output"


def run():
    OUTPUT_DIR.mkdir(exist_ok=True)
    print(f"Comparative table: {COMPARATIVE_TABLE}")
    if not os.getenv("GEMINI_API_KEY"):
        print("GEMINI_API_KEY not set — final render runs in OFFLINE MODE (mock).\n")

    # Base massing (placeholder until the real Stage 2 model is wired in).
    base_path = build_massing_placeholder(MASSING_DIR / "massing_base.png")
    print(f"Massing placeholder -> {base_path}\n")

    # Step 1: select best material per surface.
    selected = load_selected_materials(COMPARATIVE_TABLE)
    print(f"Selected {len(selected)} material(s) from the comparative table.\n")

    # Steps 2-3 loop: resolve texture + collect for application.
    textured_surfaces: list[TexturedSurface] = []
    for mat in selected:
        print(f"-- Surface: {mat.surface_id} ({mat.surface_type}) -> {mat.product_name}")
        texture = get_texture(mat, TEXTURE_DIR)
        print(f"   texture [{texture.source}] -> {Path(texture.image_path).name}")
        textured_surfaces.append(TexturedSurface(material=mat, texture=texture))

    if not textured_surfaces:
        print("No materials to visualise — nothing to do.")
        return

    # Step 3 (apply all) — "when all materials applied".
    composite_path, face_specs = apply_textures(
        textured_surfaces, OUTPUT_DIR / "textured_massing.png"
    )
    print(f"\nTextured massing -> {composite_path}")

    # Step 5: final visualisation.
    result = render_visualisation(
        composite_path=composite_path,
        face_specs=face_specs,
        out_path=OUTPUT_DIR / "final_render.png",
        project_name=PROJECT_NAME,
        site_location=SITE_LOCATION,
        building_type=BUILDING_TYPE,
    )
    print(f"Final render [{result.mode}] -> {result.image_path}")

    # Manifest for downstream / reporting.
    manifest = {
        "project": PROJECT_NAME,
        "site": SITE_LOCATION,
        "building_type": BUILDING_TYPE,
        "render_mode": result.mode,
        "render_path": result.image_path,
        "textured_massing": composite_path,
        "surfaces": [
            {
                "surface_id": ts.material.surface_id,
                "surface_type": ts.material.surface_type,
                "product_name": ts.material.product_name,
                "manufacturer": ts.material.manufacturer,
                "material_category": ts.material.material_category,
                "co2e_per_m2": ts.material.co2e_per_m2,
                "texture_source": ts.texture.source,
                "texture_path": ts.texture.image_path,
            }
            for ts in textured_surfaces
        ],
    }
    manifest_path = OUTPUT_DIR / "visualisation_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Manifest -> {manifest_path}")

    print("\n-- Visualisation Summary --------------------")
    print(f"  Surfaces visualised: {len(textured_surfaces)}")
    print(f"  Render mode:         {result.mode}")
    print(f"  Output:              {result.image_path}")
    print("---------------------------------------------")


if __name__ == "__main__":
    run()

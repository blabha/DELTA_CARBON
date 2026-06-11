"""
Render a 3D massing mock — offline, no Gemini key needed.

Reads the comparative table (Stage 3), resolves a texture per material, and
renders a real 3D box with those textures mapped onto roof / walls / floor.

Usage:
    python render_massing_3d.py
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from pipeline.massing3d import render_massing_3d
from pipeline.models import TexturedSurface
from pipeline.select_materials import load_selected_materials
from pipeline.texture_scraper import get_texture

load_dotenv()

PROJECT_NAME = "22@ Poblenou Residential Block"
SITE_LOCATION = "22@ Poblenou, Barcelona, Spain"

HERE = Path(__file__).parent
DEFAULT_TABLE = (
    HERE.parent
    / "SURROUND_UPFRONT-CARBON-bhavana (1)"
    / "SURROUND_UPFRONT-CARBON-bhavana"
    / "output"
    / "comparative_table.csv"
)
COMPARATIVE_TABLE = Path(os.getenv("COMPARATIVE_TABLE", str(DEFAULT_TABLE)))
TEXTURE_DIR = HERE / "assets" / "textures"
OUTPUT_DIR = HERE / "output"


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    selected = load_selected_materials(COMPARATIVE_TABLE)
    print(f"Selected {len(selected)} material(s).")

    textured = []
    for mat in selected:
        tex = get_texture(mat, TEXTURE_DIR)
        print(f"  {mat.surface_type:6} -> {mat.product_name}  [{tex.source}]")
        textured.append(TexturedSurface(material=mat, texture=tex))

    out = render_massing_3d(
        textured, OUTPUT_DIR / "massing_3d.png",
        project_name=PROJECT_NAME, site_location=SITE_LOCATION,
    )
    print(f"3D massing render -> {out}")


if __name__ == "__main__":
    main()

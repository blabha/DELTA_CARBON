"""
Build an interactive, manipulable 3D massing (offline, no Gemini key).

Reads the comparative table (Stage 3), resolves a texture per material, and
exports:
  - output/massing.glb          open in any 3D viewer
  - output/massing_viewer.html  double-click to orbit / pan / zoom in a browser

Usage:
    python make_interactive_3d.py
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from pipeline.interactive3d import build_glb, build_viewer_html
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

    glb = build_glb(textured, OUTPUT_DIR / "massing.glb")
    print(f"GLB model     -> {glb}")

    html = build_viewer_html(
        glb, OUTPUT_DIR / "massing_viewer.html",
        title=PROJECT_NAME, subtitle=SITE_LOCATION,
    )
    print(f"Web viewer    -> {html}")
    print("\nOpen massing_viewer.html in your browser to orbit / pan / zoom,")
    print("or open massing.glb in Windows 3D Viewer / the VS Code glTF extension.")


if __name__ == "__main__":
    main()

"""
Render a comparison set of the faithful PBR massing render, varying building,
sky (HDR), and camera angle, so the best/most-fitting look can be chosen.

Outputs: output/compare/<name>.png + output/compare/_contact_sheet.png
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

from pipeline.massing_generator import generate_massing
from pipeline.massing_loader import load_massing
from pipeline.obj_render import build_textured_submeshes, material_colour
from pipeline.select_materials import load_selected_materials
from pipeline.texture_library import get_environment, get_maps
from pipeline.texture_scraper import get_texture
from pipeline.vtk_render import render_pretty

load_dotenv()

HERE = Path(__file__).parent
TABLE = HERE / "sample_data" / "comparative_table.csv"
TEX_DIR = HERE / "assets" / "textures"
OUT = HERE / "output" / "compare"
OUT.mkdir(parents=True, exist_ok=True)
SITE = "22@ Poblenou, Barcelona, Spain"
_GROUP_TO_SURFACE = {"roof": "roof", "wall": "wall", "floor": "floor"}


def prepare(massing_obj: Path):
    selected = load_selected_materials(TABLE)
    by_type = {m.surface_type.lower(): m for m in selected}
    group_textures, group_maps, group_colours, legend = {}, {}, {}, []
    for g, st in _GROUP_TO_SURFACE.items():
        mat = by_type.get(st)
        if not mat:
            continue
        tex = get_texture(mat, TEX_DIR)
        group_textures[g] = Image.open(tex.image_path).convert("RGB")
        group_colours[g] = material_colour(tex.image_path)
        m = get_maps(mat.material_category)
        if m:
            group_maps[g] = m
        legend.append({
            "label": f"{mat.surface_type}: {mat.product_name}",
            "detail": f"{mat.co2e_per_m2:.1f} kg CO2e/m2",
            "color": group_colours[g],
        })
    if not massing_obj.exists():
        generate_massing(massing_obj)
    mesh, face_groups = load_massing(massing_obj)
    submeshes = build_textured_submeshes(mesh, face_groups, group_textures)
    return mesh, submeshes, group_maps, legend


def main():
    clean = HERE / "massing" / "generated_massing.obj"
    engel = HERE / "massing" / "imported_massing.obj"

    # Resolve skies (fall back to partly-cloudy if a slug is unavailable).
    partly = get_environment("kloofendal_48d_partly_cloudy_puresky")
    clear = get_environment("kloofendal_43d_clear_puresky") or partly
    sunset = get_environment("venice_sunset") or partly

    # (name, massing, env, elev, azim, title)
    variants = [
        ("01_clean_partlycloudy_3q", clean, partly, 20, -55, "Clean - partly cloudy - 3/4"),
        ("02_clean_clearblue_hero", clean, clear, 8, -42, "Clean - clear blue - low hero"),
        ("03_clean_sunset_3q", clean, sunset, 18, -120, "Clean - sunset - 3/4 other side"),
        ("04_engel_partlycloudy_3q", engel, partly, 18, -55, "Engel House - partly cloudy"),
    ]

    imgs = []
    cache = {}
    for name, obj, env, elev, azim, title in variants:
        if obj not in cache:
            cache[obj] = prepare(obj)
        mesh, submeshes, group_maps, legend = cache[obj]
        out = OUT / f"{name}.png"
        render_pretty(submeshes, mesh.bounds, str(out), legend=legend,
                      group_maps=group_maps, env_hdr=env, elev=elev, azim=azim,
                      project_name="SURROUND Massing - Material Study", site_location=SITE,
                      size=(1200, 850))
        print("rendered", name)
        imgs.append((title, out))

    # contact sheet 2x2 with captions
    cell = (760, 540)
    pad, cap = 12, 30
    sheet = Image.new("RGB", (cell[0] * 2 + pad * 3, (cell[1] + cap) * 2 + pad * 3), "white")
    try:
        f = ImageFont.truetype("arialbd.ttf", 20)
    except Exception:
        f = ImageFont.load_default()
    d = ImageDraw.Draw(sheet)
    for i, (title, p) in enumerate(imgs):
        im = Image.open(p).convert("RGB").resize(cell)
        x = pad + (i % 2) * (cell[0] + pad)
        y = pad + (i // 2) * (cell[1] + cap + pad)
        sheet.paste(im, (x, y))
        d.text((x + 6, y + cell[1] + 4), f"{i+1}. {title}", font=f, fill=(20, 30, 50))
    sheet.save(OUT / "_contact_sheet.png")
    print("contact sheet ->", OUT / "_contact_sheet.png")


if __name__ == "__main__":
    main()

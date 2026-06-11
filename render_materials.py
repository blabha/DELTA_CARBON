"""
Render material-swap examples on the clean massing (to showcase the enriched
library), plus the finalized hero render at full presentation resolution.

Outputs:
  output/materials/<scheme>.png      one per material scheme
  output/materials/_contact_sheet.png
  output/hero_render.png             variant #2 (clean, clear blue, hero) at 2400px
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from pipeline.massing_generator import generate_massing
from pipeline.massing_loader import load_massing
from pipeline.obj_render import build_textured_submeshes, material_colour
from pipeline.texture_library import get_environment, get_maps
from pipeline.vtk_render import render_pretty

HERE = Path(__file__).parent
MASSING = HERE / "massing" / "imported_massing.obj"
OUT = HERE / "output" / "materials"
OUT.mkdir(parents=True, exist_ok=True)
SITE = "22@ Poblenou, Barcelona, Spain"

# scheme -> {group: material category}
SCHEMES = {
    "brick_facade":  {"roof": "wood",       "wall": "brick",  "floor": "stone"},
    "stone_facade":  {"roof": "wood",       "wall": "stone",  "floor": "concrete"},
    "marble_facade": {"roof": "concrete",   "wall": "marble", "floor": "concrete"},
    "corten_green":  {"roof": "green_roof", "wall": "corten", "floor": "concrete"},
    "glass_timber":  {"roof": "wood",       "wall": "glass",  "floor": "concrete"},
}


def prepare(mesh, face_groups, scheme):
    group_textures, group_maps, legend = {}, {}, []
    for g, cat in scheme.items():
        maps = get_maps(cat)
        if not maps:
            continue
        group_textures[g] = Image.open(maps["color"]).convert("RGB")
        group_maps[g] = maps
        legend.append({"label": f"{g.title()}: {cat.replace('_', ' ').title()}",
                       "detail": "EPD material option",
                       "color": material_colour(maps["color"])})
    submeshes = build_textured_submeshes(mesh, face_groups, group_textures)
    return submeshes, group_maps, legend


def main():
    if not MASSING.exists():
        generate_massing(MASSING)
    mesh, face_groups = load_massing(MASSING)
    env = get_environment()  # clear blue (default)

    imgs = []
    for name, scheme in SCHEMES.items():
        submeshes, group_maps, legend = prepare(mesh, face_groups, scheme)
        out = OUT / f"{name}.png"
        render_pretty(submeshes, mesh.bounds, str(out), legend=legend,
                      group_maps=group_maps, env_hdr=env, elev=18, azim=-55,
                      project_name="SURROUND - Material Option", site_location=SITE,
                      size=(1200, 850))
        print("rendered", name)
        imgs.append((name.replace("_", " ").title(), out))

    # contact sheet 2x3
    cell = (640, 453); pad, cap = 12, 28; cols = 3
    rows = (len(imgs) + cols - 1) // cols
    sheet = Image.new("RGB", (cell[0]*cols + pad*(cols+1), (cell[1]+cap)*rows + pad*(rows+1)), "white")
    d = ImageDraw.Draw(sheet)
    try:
        f = ImageFont.truetype("arialbd.ttf", 20)
    except Exception:
        f = ImageFont.load_default()
    for i, (title, p) in enumerate(imgs):
        im = Image.open(p).convert("RGB").resize(cell)
        x = pad + (i % cols)*(cell[0]+pad); y = pad + (i//cols)*(cell[1]+cap+pad)
        sheet.paste(im, (x, y)); d.text((x+6, y+cell[1]+4), title, font=f, fill=(20, 30, 50))
    sheet.save(OUT / "_contact_sheet.png")
    print("contact sheet ->", OUT / "_contact_sheet.png")

    # Finalized hero: variant #2 (clean, clear blue, low hero angle) at full res.
    submeshes, group_maps, legend = prepare(mesh, face_groups,
                                            {"roof": "wood", "wall": "concrete", "floor": "steel"})
    hero = HERE / "output" / "hero_render.png"
    render_pretty(submeshes, mesh.bounds, str(hero), legend=legend,
                  group_maps=group_maps, env_hdr=env, elev=8, azim=-42,
                  project_name="SURROUND Massing - Material Study", site_location=SITE,
                  size=(2400, 1700))
    print("hero ->", hero)


if __name__ == "__main__":
    main()

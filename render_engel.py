"""Render a set of good-looking PBR shots of the Engel House."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from pipeline.massing_loader import load_massing
from pipeline.obj_render import build_textured_submeshes, material_colour
from pipeline.select_materials import load_selected_materials
from pipeline.texture_library import get_environment, get_maps
from pipeline.vtk_render import render_pretty

HERE = Path(__file__).parent
OBJ = HERE / "massing" / "imported_massing.obj"
TABLE = HERE / "sample_data" / "comparative_table.csv"
OUT = HERE / "output" / "engel"
OUT.mkdir(parents=True, exist_ok=True)
SITE = "22@ Poblenou, Barcelona, Spain"
_G = {"roof": "roof", "wall": "wall", "floor": "floor"}


def prepare():
    by = {m.surface_type.lower(): m for m in load_selected_materials(TABLE)}
    gt, gm, legend = {}, {}, []
    for g, st in _G.items():
        mat = by.get(st)
        if not mat:
            continue
        maps = get_maps(mat.material_category)
        gt[g] = Image.open(maps["color"]).convert("RGB")
        gm[g] = maps
        legend.append({"label": f"{mat.surface_type}: {mat.product_name}",
                       "detail": f"{mat.co2e_per_m2:.1f} kg CO2e/m2",
                       "color": material_colour(maps["color"])})
    mesh, fg = load_massing(OBJ)
    glass = None
    gi = fg.get("glass")
    if gi is not None and len(gi):
        glass = mesh.submesh([gi], append=True)
    return mesh, build_textured_submeshes(mesh, fg, gt), gm, legend, glass


def main():
    mesh, subs, gm, legend, glass = prepare()
    clear = get_environment("qwantani_noon_puresky")          # bright blue noon
    cloudy = get_environment("kloofendal_48d_partly_cloudy_puresky")

    shots = [
        ("01_frontleft_clear", clear, 16, -55),
        ("02_frontright_clear", clear, 14, -125),
        ("03_lowhero_cloudy", cloudy, 7, -48),
        ("04_aerial_clear", clear, 38, -60),
    ]
    imgs = []
    for name, env, elev, azim in shots:
        out = OUT / f"{name}.png"
        render_pretty(subs, mesh.bounds, str(out), legend=legend, group_maps=gm,
                      env_hdr=env, glass_mesh=glass, elev=elev, azim=azim, size=(1500, 1050),
                      project_name="Engel House - SURROUND Material Study", site_location=SITE)
        print("rendered", name)
        imgs.append((name, out))

    cell = (740, 518); pad = 12
    sheet = Image.new("RGB", (cell[0]*2+pad*3, cell[1]*2+pad*3), "white")
    for i, (n, p) in enumerate(imgs):
        im = Image.open(p).convert("RGB").resize(cell)
        sheet.paste(im, (pad+(i % 2)*(cell[0]+pad), pad+(i//2)*(cell[1]+pad)))
    sheet.save(OUT / "_contact_sheet.png")

    # full-res hero
    render_pretty(subs, mesh.bounds, str(HERE/"output"/"engel_hero.png"), legend=legend,
                  group_maps=gm, env_hdr=clear, glass_mesh=glass, elev=14, azim=-55, size=(2400, 1680),
                  project_name="Engel House - SURROUND Material Study", site_location=SITE)
    print("hero -> output/engel_hero.png")


if __name__ == "__main__":
    main()

"""Final presentation renders of the Engel House: max-res day + evening (lit windows)."""
from pathlib import Path

from render_engel import prepare
from pipeline.texture_library import get_environment
from pipeline.vtk_render import render_pretty

HERE = Path(__file__).parent
SITE = "22@ Poblenou, Barcelona, Spain"
TITLE = "Engel House - SURROUND Material Study"


def main():
    mesh, subs, gm, legend, glass = prepare()

    # Daytime hero — bright noon, reflective sky-glass, max resolution.
    render_pretty(subs, mesh.bounds, str(HERE / "output" / "final_day.png"),
                  legend=legend, group_maps=gm, glass_mesh=glass, glass_lit=False,
                  env_hdr=get_environment("qwantani_noon_puresky"),
                  elev=15, azim=-55, size=(3000, 2100),
                  project_name=TITLE, site_location=SITE)
    print("day  -> output/final_day.png")

    # Evening hero — sunset sky, warm glowing windows.
    render_pretty(subs, mesh.bounds, str(HERE / "output" / "final_evening.png"),
                  legend=legend, group_maps=gm, glass_mesh=glass, glass_lit=True,
                  env_hdr=get_environment("venice_sunset"),
                  elev=10, azim=-52, size=(3000, 2100),
                  project_name=TITLE, site_location=SITE)
    print("eve  -> output/final_evening.png")


if __name__ == "__main__":
    main()

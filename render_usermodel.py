"""
Render the imported user massing (Massing-Model 7) at Engel-House quality.

Same pipeline as render_engel.py — HDR image-based lighting + PBR *textures*
(the EPD-chosen picks) + reflective glass — so the building wears the chosen
materials and the Material Passport in the corner turns the model into the chart.

The model is a residential SLAB TOWER (~49 x 20 m footprint, ~60 m tall) authored
Y-up (must be reoriented to Z-up or it lies on its side). It is split by MATERIAL
so the elements stay clearly distinct:
  wall <- brick facade panels (with the window OPENINGS cut in) -> brick texture
  rail <- metallic balcony / guard-rail faces                  -> steel texture
  roof <- upward metal faces                                   -> StructaBoard CLT
  slab <- the dark horizontal floor plates ("diffuse_Black")   -> GreenSteel steel

The model has NO glazing geometry — the windows are just openings in the brick.
So a continuous GLASS CURTAIN is generated just behind the perforated brick
screen (make_glass_box); the window openings then read as blue reflective glazing.
"""
from pathlib import Path

import numpy as np
import trimesh
import vtk
from PIL import Image

from pipeline.massing_loader import _parse_obj, orient_to_z_up
from pipeline.obj_render import _textured_submesh, material_colour
from pipeline.select_materials import load_selected_materials
from pipeline.texture_library import get_environment, get_maps
from pipeline import vtk_render as VR

HERE = Path(__file__).parent
OBJ = HERE / "Massing-Model 7 version.obj"
TABLE = HERE / "sample_data" / "comparative_table.csv"
OUT = HERE / "output" / "usermodel"
OUT.mkdir(parents=True, exist_ok=True)
SITE = "22@ Poblenou, Barcelona, Spain"

# element -> (texture category, EPD surface-type or None=model element, base label, UV tile)
PLAN = {
    "wall": ("brick",  None,    "Wall: Brick facade",   2.5),
    "rail": ("steel",  None,    "Balcony / guard rail", 1.5),
    "roof": ("timber", "roof",  "Roof",                 2.0),
    "slab": ("steel",  "floor", "Floor",                3.0),
}
GLASS_COLOR = (0.32, 0.58, 0.88)         # sky-blue glazing


def classify(mesh, fmat):
    """Split by material: brick facade (wall) / metal balconies (rail) / dark
    floor plates (slab); peel the true roof off the upward-facing metal."""
    nz = mesh.face_normals[:, 2]
    black = np.char.find(fmat, "black") >= 0          # horizontal floor plates
    brick = (~black) & (np.char.find(fmat, "brick") >= 0)
    metal = (~black) & (np.char.find(fmat, "metal") >= 0)
    roof = metal & (nz > 0.6)
    rail = metal & ~roof
    return {"wall": np.where(brick)[0], "rail": np.where(rail)[0],
            "roof": np.where(roof)[0], "slab": np.where(black)[0]}


def make_window_glass(mesh, brick_idx, res=0.35, depth_frac=0.30):
    """Detect the discrete window OPENINGS in the brick screen and fill each with
    a glass pane (coplanar with the facade).

    For each of the four facades: rasterise the front-facing brick coverage onto a
    2D grid, close interior cracks, then `binary_fill_holes` to find the ENCLOSED
    empty regions — those are the windows (the building exterior is not enclosed,
    so it's excluded). A glass quad is emitted for every window cell. No bleed:
    glass appears only where the brick has a real opening.
    """
    from scipy.ndimage import binary_closing, binary_fill_holes, binary_opening

    fn = mesh.face_normals[brick_idx]
    fc = mesh.triangles[brick_idx].mean(axis=1)
    bb0, bb1 = mesh.bounds
    verts_all, all_faces = mesh.vertices, mesh.faces[brick_idx]

    chunks_v, chunks_f, nv = [], [], 0
    for axis, sign in [(1, -1), (1, 1), (0, -1), (0, 1)]:        # front/back/left/right
        ip = [a for a in (0, 1, 2) if a != axis]                 # in-plane axes
        plane = bb0[axis] if sign < 0 else bb1[axis]
        depth = bb1[axis] - bb0[axis]
        near = (fc[:, axis] < bb0[axis] + depth_frac * depth) if sign < 0 \
            else (fc[:, axis] > bb1[axis] - depth_frac * depth)
        sel = (fn[:, axis] * sign > 0.4) & near                  # outward-facing, outer layer
        if sel.sum() < 20:
            continue

        vid = np.unique(all_faces[sel].ravel())
        pu, pv = verts_all[vid][:, ip[0]], verts_all[vid][:, ip[1]]
        u0, u1, v0, v1 = pu.min(), pu.max(), pv.min(), pv.max()
        nu, nvv = max(8, int((u1 - u0) / res)), max(8, int((v1 - v0) / res))
        mask = np.zeros((nu, nvv), bool)
        ui = np.clip(((pu - u0) / (u1 - u0) * (nu - 1)).astype(int), 0, nu - 1)
        vi = np.clip(((pv - v0) / (v1 - v0) * (nvv - 1)).astype(int), 0, nvv - 1)
        mask[ui, vi] = True

        solid = binary_closing(mask, iterations=2)               # fill cracks in panels
        # facade silhouette = solid grown enough to bridge the openings, then the
        # openings are silhouette minus solid (catches edge-connected windows too).
        silhouette = binary_fill_holes(binary_closing(solid, iterations=8))
        windows = binary_opening(silhouette & ~solid, iterations=1)  # drop specks/slots
        wu, wv = np.where(windows)
        if len(wu) == 0:
            continue

        du, dv = (u1 - u0) / nu, (v1 - v0) / nvv
        a, b = u0 + wu * du, u0 + (wu + 1) * du
        c, d = v0 + wv * dv, v0 + (wv + 1) * dv
        q = np.zeros((len(wu), 4, 3))
        q[:, :, axis] = plane - sign * 0.06                      # just inside the facade
        q[:, :, ip[0]] = np.stack([a, b, b, a], 1)
        q[:, :, ip[1]] = np.stack([c, c, d, d], 1)
        v = q.reshape(-1, 3)
        f = np.add.outer(np.arange(len(wu)) * 4,
                         np.array([[0, 1, 2], [0, 2, 3]])).reshape(-1, 3)
        chunks_v.append(v); chunks_f.append(f + nv); nv += len(v)

    if not chunks_v:
        return None
    return trimesh.Trimesh(vertices=np.vstack(chunks_v),
                           faces=np.vstack(chunks_f), process=False)


def _planar_uv_submesh(mesh, idx, image, tile, axes=(0, 2)):
    """Memory-light textured submesh (per-vertex planar UVs, no face explosion)."""
    sub = mesh.submesh([idx], append=True)
    v = sub.vertices
    uv = np.stack([v[:, axes[0]] / tile, v[:, axes[1]] / tile], axis=1)
    sub.visual = trimesh.visual.TextureVisuals(uv=uv.astype(np.float32), image=image)
    return sub


def prepare():
    mesh, fmat = _parse_obj(OBJ)
    orient_to_z_up(mesh)                              # authored Y-up -> stand it up
    fmat = np.array([m.lower() for m in fmat])
    g = classify(mesh, fmat)
    print("  elements: " + ", ".join(f"{k}:{len(v)}" for k, v in g.items()))

    by = {m.surface_type.lower(): m for m in load_selected_materials(TABLE)}
    submeshes, group_maps, legend = [], {}, []
    for grp, (cat, st, label, tile) in PLAN.items():
        idx = g[grp]
        if len(idx) == 0:
            continue
        maps = get_maps(cat)
        img = Image.open(maps["color"]).convert("RGB")
        if len(idx) > 2_500_000:                      # only the very largest -> memory-light
            sub = _planar_uv_submesh(mesh, idx, img, tile, axes=(0, 2))
        else:
            sub = _textured_submesh(mesh, idx, img, tile)   # crisp box-projected UVs
        submeshes.append((grp, sub, img))
        group_maps[grp] = maps
        mat = by.get(st)
        if mat:
            legend.append({"label": f"{label}: {mat.product_name}",
                           "detail": f"{mat.co2e_per_m2:.1f} kg CO2e/m2",
                           "color": material_colour(maps["color"])})
        else:
            legend.append({"label": label, "detail": "model element",
                           "color": material_colour(maps["color"])})

    # Glazing: this model has NO glass surface and its brick "facade" is a ~1.8 m
    # deep 3-D lattice (balconies + reveals all in brick) with no clean window
    # plane, so automated glass extraction mismatches the real openings. We leave
    # the openings as recessed voids (they read as dark windows). To get true blue
    # glazing, re-export the model with a dedicated glass material (like the Engel
    # model's "Translucent_Glass_Gray") and set GLAZE=True.
    GLAZE = False
    glass = make_window_glass(mesh, g["wall"]) if GLAZE else None
    if glass is not None:
        legend.append({"label": "Windows: Glazing", "detail": "model element",
                       "color": GLASS_COLOR})
    return mesh.bounds.copy(), submeshes, group_maps, legend, glass


def _bright_glass(sub):
    """Sky-blue glazing. Strong ambient + specular (Phong) so it reads as bright
    glass; a headlight in the scene guarantees the camera-facing panes are lit."""
    pd = VR._plain_polydata(sub)
    m = vtk.vtkPolyDataMapper(); m.SetInputData(pd)
    a = vtk.vtkActor(); a.SetMapper(m)
    p = a.GetProperty()
    p.SetColor(*GLASS_COLOR)
    p.SetAmbient(0.55); p.SetDiffuse(0.75)
    p.SetSpecular(0.7); p.SetSpecularPower(80)
    return a


def _bright_passes(renderer, exposure=2.1):
    """Filmic tone map (brighter) over shadows; degrade gracefully."""
    try:
        tone = vtk.vtkToneMappingPass()
        tone.SetToneMappingType(vtk.vtkToneMappingPass.GenericFilmic)
        tone.SetGenericFilmicDefaultPresets(); tone.SetExposure(exposure)
        tone.SetDelegatePass(VR._shadow_camera_pass())
        renderer.SetPass(tone)
    except Exception:
        VR._setup_passes(renderer)


def _fill_lights(bounds):
    """Soft fill from above + opposite side so deep balconies don't go black."""
    (x0, y0, z0), (x1, y1, z1) = bounds
    cx, cy, cz = (x0+x1)/2, (y0+y1)/2, (z0+z1)/2
    d = float(np.linalg.norm([x1-x0, y1-y0, z1-z0]))
    out = []
    top = vtk.vtkLight(); top.SetPosition(cx, cy, cz + d*1.4); top.SetFocalPoint(cx, cy, cz)
    top.SetColor(1, 1, 1); top.SetIntensity(0.45); out.append(top)
    fill = vtk.vtkLight(); fill.SetPosition(cx + d*1.2, cy + d*0.4, cz + d*0.3)
    fill.SetFocalPoint(cx, cy, cz); fill.SetColor(0.9, 0.94, 1.0); fill.SetIntensity(0.5)
    out.append(fill)
    return out


def render(subs, gm, legend, glass, bounds, env_hdr, elev, azim, out, size, overlay=True):
    r = vtk.vtkRenderer()
    r.SetBackground(0.82, 0.86, 0.91); r.SetBackground2(0.96, 0.97, 0.99)
    r.GradientBackgroundOn(); r.AutomaticLightCreationOff(); r.UseFXAAOn()
    keep = []
    ibl = VR._setup_ibl(r, env_hdr, show_sky=False)
    if ibl:
        keep.append(ibl)
    for grp, sub, _img in subs:
        r.AddActor(VR._pbr_actor(sub, gm[grp], keep))
    try:
        r.AddActor(VR._ground_actor(bounds, get_maps("paving"), keep))
    except Exception:
        r.AddActor(VR._ground_actor(bounds))
    if glass is not None and len(glass.faces):
        r.AddActor(_bright_glass(glass))
    for L in VR._key_lights(bounds, bool(ibl)):
        r.AddLight(L)
    for L in _fill_lights(bounds):
        r.AddLight(L)
    head = vtk.vtkLight(); head.SetLightTypeToHeadlight(); head.SetIntensity(0.35)
    r.AddLight(head)                              # lights camera-facing glazing
    VR._place_camera(r, bounds, elev, azim)
    rw = vtk.vtkRenderWindow(); rw.SetOffScreenRendering(1); rw.SetMultiSamples(8)
    rw.AddRenderer(r); rw.SetSize(*size)
    _bright_passes(r); rw.Render()
    w2i = vtk.vtkWindowToImageFilter(); w2i.SetInput(rw)
    w2i.ReadFrontBufferOff(); w2i.Update()
    img = VR._postprocess(VR._vtk_image_to_pil(w2i.GetOutput()))
    if overlay:
        img = VR._add_titles(img, "Massing Model 2 - SURROUND Material Study", SITE)
        img = VR._add_legend(img, legend)
    img.save(out); print("rendered", Path(out).name)


def main():
    bounds, subs, gm, legend, glass = prepare()
    clear = get_environment("qwantani_noon_puresky")
    cloudy = get_environment("kloofendal_48d_partly_cloudy_puresky")
    shots = [
        (HERE / "output" / "usermodel_hero.png", cloudy, 12, -58, (1800, 2200)),
        (OUT / "01_corner.png", clear, 8, -120, (1500, 1900)),
        (OUT / "02_aerial.png", cloudy, 32, -60, (1700, 1700)),
        (OUT / "03_facade.png", cloudy, 4, -90, (1500, 1900)),
    ]
    for out, env, elev, azim, size in shots:
        render(subs, gm, legend, glass, bounds, env, elev, azim, str(out), size)


if __name__ == "__main__":
    main()

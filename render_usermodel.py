"""
Render the user's massing: textured + element-distinct + evenly lit.

- Detection: model materials (brick, glass) + face NORMALS (up=roof, down=floor,
  side=wall) for the rest, so elements separate properly.
- Materials: PBR base-colour TEXTURES (brick / concrete / timber) under even,
  neutral image-based lighting -> readable texture, no patchiness, no blue cast.
  Glass = bold blue, base = steel (solid, they're small/edge).
- Big facade-backing wall uses per-vertex UVs (memory-light); the smaller visible
  brick/roof use crisp per-face box projection.
"""
from pathlib import Path
import numpy as np
import trimesh
import vtk
from PIL import Image

from pipeline.massing_loader import _parse_obj, orient_to_z_up
from pipeline.obj_render import _textured_submesh, material_colour
from pipeline.select_materials import load_selected_materials
from pipeline.texture_library import get_maps
from pipeline import vtk_render as VR

HERE = Path(__file__).parent
OBJ = HERE / "Massing-Model 7 version.obj"
TABLE = HERE / "sample_data" / "comparative_table.csv"
SITE = "22@ Poblenou, Barcelona, Spain"
OUT = HERE / "output" / "usermodel"
OUT.mkdir(parents=True, exist_ok=True)

# element -> (EPD texture category, roughness, label)
ELEMENTS = {
    "brick": ("brick", 0.75, "Facade: Brick screen"),
    "wall": ("concrete", 0.80, "Wall: EcoSlab Concrete"),
    "roof": ("wood", 0.65, "Roof: StructaBoard Timber CLT"),
}
GLASS_COLOR = (0.13, 0.42, 0.82)
STEEL_COLOR = (0.28, 0.30, 0.34)


def classify(mesh, fmat):
    nz = mesh.face_normals[:, 2]
    cz = mesh.triangles[:, :, 2].mean(axis=1)
    z0, z1 = mesh.bounds[0][2], mesh.bounds[1][2]
    zn = (cz - z0) / (z1 - z0 + 1e-9)
    glass = np.char.find(fmat, "black") >= 0
    brick = (~glass) & (np.char.find(fmat, "brick") >= 0)
    rest = ~glass & ~brick
    roof = rest & (nz > 0.45) & (zn > 0.5)      # up-facing, upper part
    floor = rest & (nz < -0.45) & (zn < 0.25)   # down-facing, lower part
    wall = rest & ~roof & ~floor
    return {"brick": np.where(brick)[0], "wall": np.where(wall)[0],
            "roof": np.where(roof)[0], "floor": np.where(floor)[0],
            "glass": np.where(glass)[0]}


def _uv_cyl(sub, image, tile, bounds):
    v = sub.vertices
    (x0, y0, _), (x1, y1, _) = bounds
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    r = 0.25 * ((x1 - x0) + (y1 - y0))
    ang = np.arctan2(v[:, 1] - cy, v[:, 0] - cx)
    sub.visual = trimesh.visual.TextureVisuals(
        uv=np.stack([ang * r / tile, v[:, 2] / tile], axis=1), image=image)
    return sub


def _pbr_textured(sub, image, keep, rough):
    pd = VR._trimesh_to_polydata(sub)
    m = vtk.vtkPolyDataMapper(); m.SetInputData(pd)
    tex = vtk.vtkTexture(); tex.SetInputData(VR._pil_to_vtk_image(image))
    tex.InterpolateOn(); tex.MipmapOn(); tex.UseSRGBColorSpaceOn()
    try:
        tex.SetWrap(vtk.vtkTexture.Repeat)
    except Exception:
        tex.RepeatOn()
    keep.append(tex)
    a = vtk.vtkActor(); a.SetMapper(m)
    p = a.GetProperty(); p.SetInterpolationToPBR(); p.SetBaseColorTexture(tex)
    p.SetMetallic(0.0); p.SetRoughness(rough)
    return a


def _pbr_solid(sub, color, metal=0.0, rough=0.5):
    m = vtk.vtkPolyDataMapper(); m.SetInputData(VR._plain_polydata(sub))
    a = vtk.vtkActor(); a.SetMapper(m)
    p = a.GetProperty(); p.SetInterpolationToPBR()
    p.SetColor(*color); p.SetMetallic(metal); p.SetRoughness(rough)
    return a


def _neutral_ibl(renderer):
    h, w = 512, 1024
    yy = np.linspace(0, 1, h)[:, None]
    val = np.clip((0.78 + 0.16 * (1 - yy)) * 255, 0, 255)
    g = np.tile(val, (1, w)).astype(np.uint8)
    tex = vtk.vtkTexture()
    tex.SetInputData(VR._pil_to_vtk_image(Image.fromarray(np.stack([g, g, g], 2), "RGB")))
    tex.SetColorModeToDirectScalars(); tex.MipmapOn(); tex.InterpolateOn()
    renderer.UseImageBasedLightingOn(); renderer.SetEnvironmentTexture(tex)
    return tex


def _key_light(bounds):
    (x0, y0, z0), (x1, y1, z1) = bounds
    cx, cy, cz = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2
    d = float(np.linalg.norm([x1 - x0, y1 - y0, z1 - z0]))
    L = vtk.vtkLight()
    L.SetPosition(cx - d * 0.9, cy - d * 0.8, cz + d); L.SetFocalPoint(cx, cy, cz)
    L.SetColor(1.0, 0.99, 0.97); L.SetIntensity(0.55)
    return L


def _ground_plane(bounds, color=(0.82, 0.83, 0.85)):
    (x0, y0, z0), (x1, y1, z1) = bounds
    mx, my = (x1 - x0) * 1.1, (y1 - y0) * 1.1
    pl = vtk.vtkPlaneSource()
    pl.SetOrigin(x0 - mx, y0 - my, z0); pl.SetPoint1(x1 + mx, y0 - my, z0); pl.SetPoint2(x0 - mx, y1 + my, z0)
    m = vtk.vtkPolyDataMapper(); m.SetInputConnection(pl.GetOutputPort())
    a = vtk.vtkActor(); a.SetMapper(m)
    p = a.GetProperty(); p.SetColor(*color); p.SetAmbient(0.55); p.SetDiffuse(0.65); p.SetSpecular(0)
    return a


def main():
    mesh, fmat = _parse_obj(OBJ)
    orient_to_z_up(mesh)
    fmat = np.array([m.lower() for m in fmat])
    g = classify(mesh, fmat)
    print("  " + ", ".join(f"{k}:{len(v)}" for k, v in g.items()))
    by = {m.surface_type.lower(): m for m in load_selected_materials(TABLE)}
    bounds = mesh.bounds.copy()

    # textured submeshes: big wall via per-vertex UV; crisp brick/roof via box.
    imgs = {k: Image.open(get_maps(ELEMENTS[k][0])["color"]).convert("RGB") for k in ELEMENTS}
    textured = {}
    if len(g["wall"]):
        textured["wall"] = _uv_cyl(mesh.submesh([g["wall"]], append=True), imgs["wall"], 2.5, bounds)
    for k in ("brick", "roof"):
        if len(g[k]):
            textured[k] = _textured_submesh(mesh, g[k], imgs[k], 1.6)
    glass = mesh.submesh([g["glass"]], append=True) if len(g["glass"]) else None
    floor = mesh.submesh([g["floor"]], append=True) if len(g["floor"]) else None
    del mesh

    carbon = {"roof": by["roof"].co2e_per_m2, "wall": by["wall"].co2e_per_m2}
    legend = []
    for k in ("brick", "wall", "roof"):
        if k in textured:
            det = f"{carbon[k]:.1f} kg CO2e/m2" if k in carbon else "model element"
            legend.append({"label": ELEMENTS[k][2], "detail": det,
                           "color": material_colour(get_maps(ELEMENTS[k][0])["color"])})
    if glass is not None:
        legend.append({"label": "Windows: Glazing", "detail": "model element", "color": GLASS_COLOR})

    def render(elev, azim, out, zoom=0.7, size=(2200, 1500)):
        r = vtk.vtkRenderer()
        r.SetBackground(0.86, 0.88, 0.91); r.SetBackground2(0.96, 0.97, 0.98)
        r.GradientBackgroundOn(); r.AutomaticLightCreationOff(); r.UseFXAAOn()
        keep = [_neutral_ibl(r)]
        for k, sub in textured.items():
            r.AddActor(_pbr_textured(sub, imgs[k], keep, ELEMENTS[k][1]))
        if glass is not None:
            r.AddActor(_pbr_solid(glass, GLASS_COLOR, 0.1, 0.45))
        if floor is not None:
            r.AddActor(_pbr_solid(floor, STEEL_COLOR, 0.0, 0.5))
        r.AddActor(_ground_plane(bounds))
        r.AddLight(_key_light(bounds))
        VR._place_camera(r, bounds, elev, azim)
        r.GetActiveCamera().Zoom(zoom); r.ResetCameraClippingRange()
        rw = vtk.vtkRenderWindow(); rw.SetOffScreenRendering(1); rw.SetMultiSamples(8)
        rw.AddRenderer(r); rw.SetSize(*size)
        VR._setup_passes(r); rw.Render()
        w2i = vtk.vtkWindowToImageFilter(); w2i.SetInput(rw); w2i.ReadFrontBufferOff(); w2i.Update()
        img = VR._postprocess(VR._vtk_image_to_pil(w2i.GetOutput()))
        img = VR._add_titles(img, "SURROUND - Massing Model", SITE)
        img = VR._add_legend(img, legend)
        img.save(out); print("rendered", Path(out).name)

    render(24, -55, HERE / "output" / "usermodel_hero.png", zoom=0.62, size=(2600, 1750))
    render(16, -120, OUT / "alt_corner.png", zoom=0.7)
    render(8, -90, OUT / "alt_facade.png", zoom=0.8)


if __name__ == "__main__":
    main()

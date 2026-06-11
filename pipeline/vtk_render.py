"""
Faithful, physically-based render of the massing using VTK — free, no AI.

Renders THE actual massing geometry with the EPD-chosen materials as full PBR
surfaces (base colour + normal + occlusion/roughness/metalness) lit by an HDR
environment (image-based lighting), with a directional key light for shadows and
filmic tone mapping. This is the on-mission deliverable: your building, your
materials, your carbon — looking realistic, faithful to the model.

Falls back gracefully (PBR->Phong actor, IBL optional, passes optional) so it
always produces an image.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import vtk
from PIL import Image, ImageDraw, ImageEnhance, ImageFont
from vtk.util import numpy_support as nps


def render_pretty(
    submeshes: list,                 # [(group, trimesh_with_uv, pil_image), ...]
    bounds: np.ndarray,
    out_path: str | Path,
    project_name: str = "",
    site_location: str = "",
    legend: list | None = None,
    group_maps: dict | None = None,  # {group: {"color","normal","orm"}}
    env_hdr: str | None = None,
    glass_mesh=None,                 # trimesh of window/glazing faces
    glass_lit: bool = False,         # warm interior glow (evening look)
    elev: float = 20.0,
    azim: float = -55.0,
    size: tuple[int, int] = (1600, 1150),
) -> str:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    group_maps = group_maps or {}

    renderer = vtk.vtkRenderer()
    renderer.SetBackground(0.80, 0.85, 0.90)       # clean light studio backdrop
    renderer.SetBackground2(0.95, 0.96, 0.98)
    renderer.GradientBackgroundOn()
    renderer.AutomaticLightCreationOff()
    renderer.UseFXAAOn()

    _keep = []  # keep texture/reader refs alive
    if env_hdr:
        _keep.append(_setup_ibl(renderer, env_hdr, show_sky=False))

    # Building actors — PBR if maps available, else textured Phong.
    for group, sub, image in submeshes:
        if group in group_maps:
            renderer.AddActor(_pbr_actor(sub, group_maps[group], _keep))
        else:
            renderer.AddActor(_textured_actor(sub, image))

    ground_maps = None
    try:
        from pipeline.texture_library import get_maps as _gm
        ground_maps = _gm("paving")
    except Exception:
        pass
    renderer.AddActor(_ground_actor(bounds, ground_maps, _keep))
    if glass_mesh is not None and len(glass_mesh.faces):
        renderer.AddActor(_glass_actor(glass_mesh, lit=glass_lit))
    for light in _key_lights(bounds, bool(env_hdr)):
        renderer.AddLight(light)

    _place_camera(renderer, bounds, elev, azim)

    rw = vtk.vtkRenderWindow()
    rw.SetOffScreenRendering(1)
    rw.SetMultiSamples(8)
    rw.AddRenderer(renderer)
    rw.SetSize(*size)

    _setup_passes(renderer)

    rw.Render()

    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(rw)
    w2i.SetScale(2)
    w2i.ReadFrontBufferOff()
    w2i.Update()
    img = _vtk_image_to_pil(w2i.GetOutput()).resize(size, Image.LANCZOS)

    img = _postprocess(img)
    img = _add_titles(img, project_name, site_location)
    if legend:
        img = _add_legend(img, legend)
    img.save(out_path)
    return str(out_path)


# ── PBR + IBL ─────────────────────────────────────────────────────────────────

def _pbr_actor(sub, maps, keep) -> vtk.vtkActor:
    pd = _polydata_with_tangents(sub)
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(pd)
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    p = actor.GetProperty()
    p.SetInterpolationToPBR()
    p.SetMetallic(1.0)
    p.SetRoughness(1.0)

    base = _texture(maps.get("color"), srgb=True)
    if base:
        p.SetBaseColorTexture(base); keep.append(base)
    orm = _texture(maps.get("orm"))
    if orm:
        p.SetORMTexture(orm); keep.append(orm)
    nrm = _texture(maps.get("normal"))
    if nrm:
        p.SetNormalTexture(nrm); p.SetNormalScale(1.0); keep.append(nrm)
    return actor


def _texture(path, srgb=False):
    if not path or not Path(path).exists():
        return None
    t = vtk.vtkTexture()
    t.SetInputData(_pil_to_vtk_image(Image.open(path)))
    t.InterpolateOn()
    t.MipmapOn()
    if srgb:
        t.UseSRGBColorSpaceOn()
    try:
        t.SetWrap(vtk.vtkTexture.Repeat)
    except Exception:
        t.RepeatOn()
    return t


def _setup_ibl(renderer, env_hdr, show_sky=False):
    try:
        reader = vtk.vtkHDRReader()
        reader.SetFileName(env_hdr)
        reader.Update()
        env = vtk.vtkTexture()
        env.SetColorModeToDirectScalars()
        env.MipmapOn()
        env.InterpolateOn()
        env.SetInputConnection(reader.GetOutputPort())
        renderer.UseImageBasedLightingOn()
        renderer.SetEnvironmentTexture(env)
        refs = [reader, env]
        if show_sky:
            sky = vtk.vtkSkybox()
            sky.SetProjection(vtk.vtkSkybox.Sphere)
            sky.SetTexture(env)
            renderer.AddActor(sky)
            refs.append(sky)
        return tuple(refs)
    except Exception as exc:
        print(f"[ibl] disabled ({exc})")
        return None


def _polydata_with_tangents(sub):
    pd = _trimesh_to_polydata(sub)
    try:
        tg = vtk.vtkPolyDataTangents()
        tg.SetInputData(pd)
        tg.Update()
        return tg.GetOutput()
    except Exception:
        return pd


# ── actors / lights / camera ─────────────────────────────────────────────────

def _textured_actor(sub, pil_image) -> vtk.vtkActor:
    pd = _trimesh_to_polydata(sub)
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(pd)
    texture = vtk.vtkTexture()
    texture.SetInputData(_pil_to_vtk_image(pil_image))
    texture.InterpolateOn()
    texture.MipmapOn()
    try:
        texture.SetWrap(vtk.vtkTexture.Repeat)
    except Exception:
        texture.RepeatOn()
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.SetTexture(texture)
    p = actor.GetProperty()
    p.SetAmbient(0.32); p.SetDiffuse(0.82); p.SetSpecular(0.12); p.SetSpecularPower(28)
    return actor


def _glass_actor(sub, lit=False) -> vtk.vtkActor:
    """Glazing: reflective sky-glass by day, warm glowing windows when `lit`."""
    pd = _plain_polydata(sub)
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(pd)
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    p = actor.GetProperty()
    if lit:                                # warm interior glow (evening)
        p.SetColor(1.0, 0.84, 0.52)
        p.SetAmbient(1.0)
        p.SetDiffuse(0.25)
        p.SetSpecular(0.2)
        try:
            p.SetEmissiveFactor(1.0, 0.80, 0.48)
        except Exception:
            pass
    else:                                  # bright reflective sky-glass (day)
        p.SetInterpolationToPBR()
        p.SetColor(0.17, 0.23, 0.31)
        p.SetMetallic(0.9)
        p.SetRoughness(0.05)
    return actor


def _plain_polydata(sub) -> vtk.vtkPolyData:
    pts = vtk.vtkPoints()
    pts.SetData(nps.numpy_to_vtk(np.ascontiguousarray(sub.vertices, dtype=np.float64), deep=True))
    faces = np.ascontiguousarray(sub.faces, dtype=np.int64)
    cells = np.hstack([np.full((len(faces), 1), 3, dtype=np.int64), faces]).ravel()
    ca = vtk.vtkCellArray()
    ca.SetCells(len(faces), nps.numpy_to_vtkIdTypeArray(cells, deep=True))
    pd = vtk.vtkPolyData()
    pd.SetPoints(pts)
    pd.SetPolys(ca)
    nrm = vtk.vtkPolyDataNormals()
    nrm.SetInputData(pd)
    nrm.ComputePointNormalsOn()
    nrm.Update()
    return nrm.GetOutput()


def _ground_actor(bounds, maps=None, keep=None) -> vtk.vtkActor:
    (x0, y0, z0), (x1, y1, z1) = bounds
    mx, my = (x1 - x0) * 0.9, (y1 - y0) * 0.9
    plane = vtk.vtkPlaneSource()
    plane.SetOrigin(x0 - mx, y0 - my, z0)
    plane.SetPoint1(x1 + mx, y0 - my, z0)
    plane.SetPoint2(x0 - mx, y1 + my, z0)
    mapper = vtk.vtkPolyDataMapper()
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    pr = actor.GetProperty()
    pr.SetInterpolationToPBR()
    pr.SetMetallic(0.0)
    pr.SetRoughness(0.9)

    if maps and maps.get("color"):
        span_x = (x1 - x0) + 2 * mx
        span_y = (y1 - y0) + 2 * my
        tt = vtk.vtkTransformTextureCoords()
        tt.SetInputConnection(plane.GetOutputPort())
        tt.SetScale(max(1, span_x / 4.0), max(1, span_y / 4.0), 1)
        mapper.SetInputConnection(tt.GetOutputPort())
        base = _texture(maps.get("color"), srgb=True)
        if base:
            pr.SetBaseColorTexture(base)
            if keep is not None:
                keep.append(base)
        orm = _texture(maps.get("orm"))
        if orm:
            pr.SetORMTexture(orm)
            if keep is not None:
                keep.append(orm)
    else:
        mapper.SetInputConnection(plane.GetOutputPort())
        pr.SetColor(0.86, 0.87, 0.88)
    return actor


def _key_lights(bounds, has_ibl):
    (x0, y0, z0), (x1, y1, z1) = bounds
    cx, cy, cz = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2
    diag = float(np.linalg.norm([x1 - x0, y1 - y0, z1 - z0]))
    key = vtk.vtkLight()
    key.SetPosition(cx - diag * 1.1, cy - diag * 0.9, cz + diag * 0.9)
    key.SetFocalPoint(cx, cy, cz)
    key.SetColor(1.0, 0.96, 0.88)
    key.SetIntensity(1.3 if has_ibl else 1.4)
    lights = [key]
    if not has_ibl:
        fill = vtk.vtkLight()
        fill.SetPosition(cx + diag * 1.1, cy - diag * 0.2, cz + diag * 0.6)
        fill.SetFocalPoint(cx, cy, cz)
        fill.SetColor(0.80, 0.87, 1.0)
        fill.SetIntensity(0.5)
        lights.append(fill)
    return lights


def _place_camera(renderer, bounds, elev, azim):
    import math
    (x0, y0, z0), (x1, y1, z1) = bounds
    renderer.ResetCamera(x0, x1, y0, y1, z0, z1)
    cam = renderer.GetActiveCamera()
    fp = np.array(cam.GetFocalPoint())
    dist = cam.GetDistance()
    el, az = math.radians(elev), math.radians(azim)
    direction = np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)])
    cam.SetPosition(*(fp + direction * dist))
    cam.SetViewUp(0, 0, 1)
    cam.SetViewAngle(30)
    renderer.ResetCameraClippingRange()
    cam.Zoom(0.92)                          # pull back so the whole massing fits


def _shadow_camera_pass():
    shadows = vtk.vtkShadowMapPass()
    seq = vtk.vtkSequencePass()
    passes = vtk.vtkRenderPassCollection()
    passes.AddItem(shadows.GetShadowMapBakerPass())
    passes.AddItem(shadows)
    seq.SetPasses(passes)
    cam = vtk.vtkCameraPass()
    cam.SetDelegatePass(seq)
    return cam


def _setup_passes(renderer):
    """Filmic tone mapping over shadows; fall back to shadows, then nothing."""
    try:
        tone = vtk.vtkToneMappingPass()
        tone.SetToneMappingType(vtk.vtkToneMappingPass.GenericFilmic)
        tone.SetGenericFilmicDefaultPresets()
        tone.SetExposure(1.35)          # brighter, sunnier look
        tone.SetDelegatePass(_shadow_camera_pass())
        renderer.SetPass(tone)
        return
    except Exception:
        pass
    try:
        renderer.SetPass(_shadow_camera_pass())
    except Exception:
        pass


# ── conversions ─────────────────────────────────────────────────────────────

def _trimesh_to_polydata(sub) -> vtk.vtkPolyData:
    pts = vtk.vtkPoints()
    pts.SetData(nps.numpy_to_vtk(np.ascontiguousarray(sub.vertices, dtype=np.float64), deep=True))
    faces = np.ascontiguousarray(sub.faces, dtype=np.int64)
    cells = np.hstack([np.full((len(faces), 1), 3, dtype=np.int64), faces]).ravel()
    ca = vtk.vtkCellArray()
    ca.SetCells(len(faces), nps.numpy_to_vtkIdTypeArray(cells, deep=True))
    pd = vtk.vtkPolyData()
    pd.SetPoints(pts)
    pd.SetPolys(ca)
    uv = np.ascontiguousarray(sub.visual.uv, dtype=np.float32)
    tc = nps.numpy_to_vtk(uv, deep=True)
    tc.SetName("tc")
    pd.GetPointData().SetTCoords(tc)
    nrm = vtk.vtkPolyDataNormals()
    nrm.SetInputData(pd)
    nrm.SplittingOff()
    nrm.ComputePointNormalsOn()
    nrm.Update()
    return nrm.GetOutput()


def _pil_to_vtk_image(pil_image) -> vtk.vtkImageData:
    arr = np.asarray(pil_image.convert("RGB"))[::-1]
    h, w, _ = arr.shape
    img = vtk.vtkImageData()
    img.SetDimensions(w, h, 1)
    flat = np.ascontiguousarray(arr.reshape(-1, 3), dtype=np.uint8)
    img.GetPointData().SetScalars(nps.numpy_to_vtk(flat, deep=True, array_type=vtk.VTK_UNSIGNED_CHAR))
    return img


def _vtk_image_to_pil(vtk_img) -> Image.Image:
    w, h, _ = vtk_img.GetDimensions()
    vtk_arr = vtk_img.GetPointData().GetScalars()
    comps = vtk_arr.GetNumberOfComponents()
    arr = nps.vtk_to_numpy(vtk_arr).reshape(h, w, comps)[::-1]
    return Image.fromarray(arr[:, :, :3].astype(np.uint8), "RGB")


# ── post / titles / legend ────────────────────────────────────────────────────

def _postprocess(img: Image.Image) -> Image.Image:
    img = ImageEnhance.Contrast(img).enhance(1.06)
    img = ImageEnhance.Color(img).enhance(1.08)
    w, h = img.size
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    mask = np.clip(1.0 - 0.25 * np.clip(r - 0.65, 0, None) ** 2, 0.62, 1.0)
    arr = (np.asarray(img, dtype=float) * mask[:, :, None]).clip(0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def _font(size):
    for name in ("arialbd.ttf", "arial.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _add_titles(img, project_name, site_location) -> Image.Image:
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rectangle([0, 0, img.width, 96], fill=(255, 255, 255, 150))
    if project_name:
        draw.text((28, 18), project_name, font=_font(34), fill=(26, 58, 92))
    if site_location:
        draw.text((30, 60), site_location, font=_font(20), fill=(42, 125, 111))
    return img


def _add_legend(img, legend) -> Image.Image:
    draw = ImageDraw.Draw(img, "RGBA")
    title_f, label_f, detail_f = _font(20), _font(18), _font(15)
    sw, pad, row_h = 24, 16, 38
    title = "Material Passport"

    # Size the box to the longest line so nothing overflows.
    text_w = draw.textlength(title, font=title_f)
    for item in legend:
        text_w = max(text_w, sw + 12 + draw.textlength(item["label"], font=label_f))
        text_w = max(text_w, sw + 12 + draw.textlength(item["detail"], font=detail_f))
    width = int(text_w) + pad * 2
    height = pad * 2 + 26 + row_h * len(legend)
    x0, y0 = 24, img.height - height - 24

    draw.rectangle([x0, y0, x0 + width, y0 + height], fill=(255, 255, 255, 235),
                   outline=(26, 58, 92, 255), width=2)
    draw.text((x0 + pad, y0 + pad), title, font=title_f, fill=(26, 58, 92))
    y = y0 + pad + 28
    for item in legend:
        c = tuple(int(round(v * 255)) for v in item["color"][:3])
        draw.rectangle([x0 + pad, y + 2, x0 + pad + sw, y + 2 + sw], fill=c, outline=(80, 80, 80))
        draw.text((x0 + pad + sw + 12, y), item["label"], font=label_f, fill=(30, 30, 30))
        draw.text((x0 + pad + sw + 12, y + 19), item["detail"], font=detail_f, fill=(90, 90, 90))
        y += row_h
    return img

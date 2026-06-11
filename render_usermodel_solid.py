"""Diagnostic: render the user's full model with solid per-material colours."""
from pathlib import Path
import numpy as np
import vtk
from vtk.util import numpy_support as nps

from pipeline.massing_loader import _parse_obj
from pipeline.texture_library import get_environment
from pipeline import vtk_render as VR

HERE = Path(__file__).parent
OBJ = HERE / "Massing-Model 7 version.obj"

COLORS = {"metal": (180, 185, 190), "brick": (150, 80, 65), "black": (30, 34, 44)}


def main():
    mesh, fmat = _parse_obj(OBJ)
    fmat = np.array([m.lower() for m in fmat])
    print("faces", len(mesh.faces), "extents", np.round(mesh.extents, 2))

    # face colours by material
    fc = np.full((len(mesh.faces), 3), 200, np.uint8)
    for key, col in COLORS.items():
        fc[np.char.find(fmat, key) >= 0] = col

    # polydata for the full mesh
    pts = vtk.vtkPoints()
    pts.SetData(nps.numpy_to_vtk(np.ascontiguousarray(mesh.vertices, np.float64), deep=True))
    faces = np.ascontiguousarray(mesh.faces, np.int64)
    cells = np.hstack([np.full((len(faces), 1), 3, np.int64), faces]).ravel()
    ca = vtk.vtkCellArray()
    ca.SetCells(len(faces), nps.numpy_to_vtkIdTypeArray(cells, deep=True))
    pd = vtk.vtkPolyData(); pd.SetPoints(pts); pd.SetPolys(ca)
    pd.GetCellData().SetScalars(nps.numpy_to_vtk(fc, deep=True, array_type=vtk.VTK_UNSIGNED_CHAR))
    nrm = vtk.vtkPolyDataNormals(); nrm.SetInputData(pd); nrm.ComputeCellNormalsOn(); nrm.Update()

    mapper = vtk.vtkPolyDataMapper(); mapper.SetInputConnection(nrm.GetOutputPort())
    mapper.SetScalarModeToUseCellData(); mapper.SetColorModeToDirectScalars()
    actor = vtk.vtkActor(); actor.SetMapper(mapper)
    actor.GetProperty().SetAmbient(0.35); actor.GetProperty().SetDiffuse(0.8)

    renderer = vtk.vtkRenderer()
    renderer.SetBackground(0.80, 0.85, 0.90); renderer.SetBackground2(0.95, 0.96, 0.98)
    renderer.GradientBackgroundOn(); renderer.AutomaticLightCreationOff(); renderer.UseFXAAOn()
    keep = VR._setup_ibl(renderer, get_environment("qwantani_noon_puresky"), show_sky=False)
    renderer.AddActor(actor)
    renderer.AddActor(VR._ground_actor(mesh.bounds))
    for L in VR._key_lights(mesh.bounds, True):
        renderer.AddLight(L)
    VR._place_camera(renderer, mesh.bounds, 18, -55)

    rw = vtk.vtkRenderWindow(); rw.SetOffScreenRendering(1); rw.SetMultiSamples(8)
    rw.AddRenderer(renderer); rw.SetSize(1800, 1260)
    VR._setup_passes(renderer)
    rw.Render()
    w2i = vtk.vtkWindowToImageFilter(); w2i.SetInput(rw); w2i.ReadFrontBufferOff(); w2i.Update()
    img = VR._vtk_image_to_pil(w2i.GetOutput())
    img = VR._add_titles(img, "SURROUND - Massing Model (geometry check)", "Metal=grey  brick=red  black=dark")
    out = HERE / "output" / "usermodel_solid.png"
    img.save(out); print("->", out)


if __name__ == "__main__":
    main()

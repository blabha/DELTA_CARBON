"""
CC0 PBR texture library (ambientCG) + HDR environment (Poly Haven).

Downloads full material map sets (colour / normal / roughness / metalness / AO)
once, packs an ORM map for PBR rendering, and exposes get_maps(category). Also
fetches a small HDR for image-based lighting. Everything is CC0.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import requests
from PIL import Image

_HDR = {"User-Agent": "Mozilla/5.0 (SURROUND)"}
_ROOT = Path(__file__).parent.parent / "assets" / "textures" / "lib"
_ENV = Path(__file__).parent.parent / "assets" / "env"

# Material key -> ambientCG asset id (all CC0). Expand freely.
_ASSETS = {
    "concrete": "Concrete034",
    "wood": "WoodFloor043",
    "timber": "WoodSiding004",
    "steel": "Metal032",
    "aluminium": "Metal046A",
    "brick": "Bricks075A",
    "stone": "Travertine003",
    "marble": "Marble016",
    "tile": "Tiles093",
    "plaster": "PaintedPlaster004",
    "terracotta": "Bricks066",
    "roof_tiles": "RoofingTiles010",
    "corten": "Rust004",
    "green_roof": "Grass004",
    "glass": "Facade009",
    "paving": "PavingStones070",      # used for the ground plane
}
# Synonyms from EPD/material categories -> a material key above.
_ALIASES = {
    "concrete": "concrete", "cement": "concrete", "mineral": "concrete", "precast": "concrete",
    "wood": "wood", "clt": "wood", "cross-laminated": "wood", "glulam": "wood",
    "timber": "timber", "wood cladding": "timber", "siding": "timber",
    "steel": "steel", "metal": "steel", "iron": "steel",
    "aluminium": "aluminium", "aluminum": "aluminium",
    "brick": "brick", "masonry": "brick", "blockwork": "brick",
    "stone": "stone", "travertine": "stone", "limestone": "stone", "sandstone": "stone",
    "marble": "marble", "granite": "marble",
    "tile": "tile", "ceramic": "tile", "porcelain": "tile",
    "plaster": "plaster", "render": "plaster", "stucco": "plaster", "gypsum": "plaster",
    "terracotta": "terracotta", "clay": "terracotta",
    "roof_tiles": "roof_tiles", "roof tile": "roof_tiles", "clay tile": "roof_tiles",
    "corten": "corten", "cor-ten": "corten", "weathering steel": "corten", "rust": "corten",
    "green_roof": "green_roof", "green roof": "green_roof", "sedum": "green_roof",
    "living roof": "green_roof", "vegetation": "green_roof", "grass": "green_roof",
    "glass": "glass", "glazing": "glass", "curtain wall": "glass", "window": "glass",
    "paving": "paving",
}

# Preferred source: Poly Haven CC0 textures (higher quality, packed ARM maps).
# material key -> Poly Haven texture slug. Others fall back to ambientCG above.
_POLYHAVEN = {
    "concrete": "concrete_wall_004",
    "wood": "brown_planks_03",
    "timber": "brown_planks_05",
    "steel": "metal_plate",
    "aluminium": "metal_plate_02",
    "brick": "brick_wall_006",
    "tile": "rectangular_facade_tiles",
    "plaster": "grey_plaster_02",
    "paving": "concrete_tiles_02",
}

# Poly Haven CC0 HDRI for image-based lighting (clear blue default).
_ENV_SLUG = "kloofendal_43d_clear_puresky"


def get_maps(category: str) -> dict | None:
    """Return {'color','normal','orm'} paths for a category, downloading if needed."""
    stem = _ALIASES.get(category.lower())
    if not stem:
        return None
    folder = _ROOT / stem
    if not (folder / "Color.jpg").exists():
        try:
            _download_material(stem)
        except Exception as exc:
            print(f"[lib] could not fetch '{stem}': {exc}")
            return None
    maps = {}
    for key, fn in (("color", "Color.jpg"), ("normal", "Normal.jpg"), ("orm", "ORM.jpg")):
        p = folder / fn
        if p.exists():
            maps[key] = str(p)
    return maps or None


def get_environment(slug: str | None = None) -> str | None:
    """Return path to a Poly Haven HDR environment (1k), downloading if needed."""
    slug = slug or _ENV_SLUG
    _ENV.mkdir(parents=True, exist_ok=True)
    dest = _ENV / f"{slug}_1k.hdr"
    if not dest.exists():
        url = f"https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/1k/{slug}_1k.hdr"
        try:
            r = requests.get(url, headers=_HDR, timeout=60)
            r.raise_for_status()
            dest.write_bytes(r.content)
        except Exception as exc:
            print(f"[env] HDR download failed for {slug}: {exc}")
            return None
    return str(dest)


# ── download + ORM packing ──────────────────────────────────────────────────

def _download_material(stem: str):
    """Fetch a material: Poly Haven first (better), ambientCG as fallback."""
    folder = _ROOT / stem
    folder.mkdir(parents=True, exist_ok=True)
    if stem in _POLYHAVEN:
        try:
            _download_polyhaven(stem, _POLYHAVEN[stem], folder)
            return
        except Exception as exc:
            print(f"[lib] Poly Haven failed for {stem} ({exc}); trying ambientCG.")
    _download_ambientcg(stem, folder)


def _download_polyhaven(stem: str, slug: str, folder: Path):
    files = requests.get(f"https://api.polyhaven.com/files/{slug}", headers=_HDR, timeout=40).json()

    def url(*names):
        for n in names:
            node = files.get(n)
            if node:
                for res in ("2k", "1k"):           # prefer 2K for crispness
                    if res in node and "jpg" in node[res]:
                        return node[res]["jpg"]["url"]
        return None

    color = url("Diffuse", "diffuse", "col")
    normal = url("nor_gl", "nor_dx")
    arm = url("arm")           # AO(R)/Roughness(G)/Metalness(B) == VTK ORM

    if not color:
        raise RuntimeError("no diffuse map")
    _fetch(color, folder / "Color.jpg")
    if normal:
        _fetch(normal, folder / "Normal.jpg")
    if arm:
        _fetch(arm, folder / "ORM.jpg")
    else:  # build ORM from separate maps if no packed arm
        size = Image.open(folder / "Color.jpg").size
        ao = _fetch_gray(url("AO"), size, 255)
        rough = _fetch_gray(url("Rough"), size, 150)
        metal = _fetch_gray(url("metal"), size, 0)
        Image.merge("RGB", [ao, rough, metal]).save(folder / "ORM.jpg", quality=92)


def _fetch(url: str, dest: Path):
    r = requests.get(url, headers=_HDR, timeout=60)
    r.raise_for_status()
    img = Image.open(io.BytesIO(r.content)).convert("RGB")
    img.save(dest, quality=92)


def _fetch_gray(url, size, default: int) -> Image.Image:
    if url:
        r = requests.get(url, headers=_HDR, timeout=60)
        if r.ok:
            return Image.open(io.BytesIO(r.content)).convert("L").resize(size)
    return Image.new("L", size, default)


def _download_ambientcg(stem: str, folder: Path):
    asset = _ASSETS[stem]
    url = f"https://ambientcg.com/get?file={asset}_1K-JPG.zip"
    r = requests.get(url, headers=_HDR, timeout=60)
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))

    def find(token):
        for n in z.namelist():
            if token.lower() in n.lower() and n.lower().endswith((".jpg", ".png")):
                return n
        return None

    # Colour + normal (prefer GL convention).
    _save(z, find("Color"), folder / "Color.jpg")
    _save(z, find("NormalGL") or find("Normal"), folder / "Normal.jpg")

    # Pack ORM (R=AO, G=Roughness, B=Metalness) with sensible defaults.
    size = Image.open(folder / "Color.jpg").size
    ao = _gray(z, find("AmbientOcclusion"), size, 255)
    rough = _gray(z, find("Roughness"), size, 150)
    metal = _gray(z, find("Metalness") or find("Metallic"), size, 0)
    Image.merge("RGB", [ao, rough, metal]).save(folder / "ORM.jpg", quality=92)


def _save(z, name, dest: Path):
    if name:
        dest.write_bytes(z.read(name))


def _gray(z, name, size, default: int) -> Image.Image:
    if name:
        return Image.open(io.BytesIO(z.read(name))).convert("L").resize(size)
    return Image.new("L", size, default)


if __name__ == "__main__":
    for cat in _ASSETS:
        print(cat, "->", get_maps(cat))
    print("env ->", get_environment())

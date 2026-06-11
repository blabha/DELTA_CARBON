"""
Step 2 — Get material texture.

Tries to scrape a representative texture image from the manufacturer's website,
and falls back to a bundled/procedural texture keyed by material category when
scraping is unavailable or fails (no URL, no network, no bs4, etc.).

Scraping strategy (best-effort, never fatal):
  - resolve a candidate manufacturer URL (from MANUFACTURER_URLS, else a guess),
  - fetch the page, look for an og:image / large <img>,
  - download it as the texture.

Fallback strategy:
  - generate a deterministic procedural texture for the category so the rest of
    the pipeline always has an image to apply.
"""

from __future__ import annotations

import random
import re
from pathlib import Path
from urllib.parse import urljoin

import requests

from .models import SelectedMaterial, TextureAsset

try:  # optional, nicer scraping if present
    from bs4 import BeautifulSoup  # type: ignore
    _HAS_BS4 = True
except Exception:  # pragma: no cover
    _HAS_BS4 = False

from PIL import Image, ImageDraw, ImageFilter

_HEADERS = {"User-Agent": "Mozilla/5.0 (SURROUND visualisation bot)"}
_TIMEOUT = 8

# Known manufacturer homepages can be added here as the team confirms them.
# Keys are matched case-insensitively against the manufacturer name substring.
MANUFACTURER_URLS: dict[str, str] = {
    # "austimber innovations": "https://www.austimber.example/products",
}

# Base palettes for procedural fallbacks (R, G, B).
_PALETTES: dict[str, tuple[int, int, int]] = {
    "wood": (150, 100, 55),
    "timber": (150, 100, 55),
    "concrete": (170, 170, 168),
    "steel": (140, 145, 152),
    "metal": (140, 145, 152),
    "brick": (150, 70, 55),
    "glass": (150, 195, 205),
    "stone": (130, 128, 120),
    "insulation": (200, 190, 150),
}


def get_texture(material: SelectedMaterial, out_dir: str | Path) -> TextureAsset:
    """Resolve a texture for one selected material."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{material.surface_id}_{material.material_category}.png"

    url = _resolve_manufacturer_url(material)
    if url:
        scraped = _try_scrape_texture(url, dest)
        if scraped:
            return TextureAsset(
                surface_id=material.surface_id,
                material_category=material.material_category,
                image_path=str(dest),
                source="scraped",
                source_url=scraped,
            )

    # Preferred fallback: real CC0 texture from the bundled library.
    lib = _library_texture(material.material_category)
    if lib is not None:
        return TextureAsset(
            surface_id=material.surface_id,
            material_category=material.material_category,
            image_path=str(lib),
            source="library",
            source_url=url,
        )

    # Last resort: procedural texture for the category.
    _generate_procedural_texture(material.material_category, dest)
    return TextureAsset(
        surface_id=material.surface_id,
        material_category=material.material_category,
        image_path=str(dest),
        source="procedural",
        source_url=url,
    )


# Bundled CC0 texture library (from ambientCG). Category aliases -> file stem.
_LIBRARY_DIR = Path(__file__).parent.parent / "assets" / "textures" / "lib"
_LIBRARY_ALIASES = {
    "wood": "wood", "timber": "wood", "clt": "wood",
    "concrete": "concrete", "cement": "concrete", "mineral": "concrete",
    "steel": "steel", "metal": "steel", "aluminium": "steel", "aluminum": "steel",
}


def _library_texture(category: str):
    # Prefer the full PBR library (per-material Color.jpg), downloading if needed.
    try:
        from .texture_library import get_maps
        maps = get_maps(category)
        if maps and maps.get("color"):
            return Path(maps["color"])
    except Exception:
        pass
    # Legacy flat files (concrete.jpg / steel.jpg / wood.jpg).
    stem = _LIBRARY_ALIASES.get(category.lower())
    if stem:
        for ext in (".jpg", ".png"):
            path = _LIBRARY_DIR / f"{stem}{ext}"
            if path.exists():
                return path
    return None


# ── scraping ──────────────────────────────────────────────────────────────────

def _resolve_manufacturer_url(material: SelectedMaterial) -> str | None:
    name = material.manufacturer.lower().strip()
    for key, url in MANUFACTURER_URLS.items():
        if key in name:
            return url
    # No confirmed URL — we don't blindly guess domains (too unreliable).
    # Returning None routes us straight to the deterministic fallback.
    return None


def _try_scrape_texture(page_url: str, dest: Path) -> str | None:
    """Fetch the page, find a likely texture image, download it. Best-effort."""
    try:
        resp = requests.get(page_url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        html = resp.text
    except Exception as exc:  # pragma: no cover - network dependent
        print(f"   [scrape] could not load {page_url}: {exc}")
        return None

    img_url = _find_image_url(html, page_url)
    if not img_url:
        print("   [scrape] no suitable image found on page")
        return None

    try:
        img_resp = requests.get(img_url, headers=_HEADERS, timeout=_TIMEOUT)
        img_resp.raise_for_status()
        dest.write_bytes(img_resp.content)
        # Validate + normalise to PNG so downstream is uniform.
        with Image.open(dest) as im:
            im.convert("RGB").save(dest, "PNG")
        print(f"   [scrape] texture downloaded from {img_url}")
        return img_url
    except Exception as exc:  # pragma: no cover - network dependent
        print(f"   [scrape] image download failed: {exc}")
        return None


def _find_image_url(html: str, base_url: str) -> str | None:
    if _HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            return urljoin(base_url, og["content"])
        img = soup.find("img")
        if img and img.get("src"):
            return urljoin(base_url, img["src"])
        return None
    # Regex fallback when bs4 is absent.
    m = re.search(r'property=["\']og:image["\']\s+content=["\']([^"\']+)', html)
    if m:
        return urljoin(base_url, m.group(1))
    m = re.search(r'<img[^>]+src=["\']([^"\']+)', html)
    if m:
        return urljoin(base_url, m.group(1))
    return None


# ── procedural fallback textures ────────────────────────────────────────────────

def _generate_procedural_texture(category: str, dest: Path, size: int = 512) -> None:
    """Create a deterministic, category-appropriate texture swatch."""
    cat = category.lower()
    base = _PALETTES.get(cat, (160, 160, 160))
    rng = random.Random(hash(cat) & 0xFFFFFFFF)

    img = Image.new("RGB", (size, size), base)
    draw = ImageDraw.Draw(img)

    if cat in ("wood", "timber"):
        _draw_wood(draw, size, base, rng)
    elif cat in ("steel", "metal"):
        _draw_brushed_metal(draw, size, base, rng)
    elif cat == "brick":
        _draw_brick(draw, size, base, rng)
    elif cat == "glass":
        _draw_glass(draw, size, base, rng)
    else:  # concrete / stone / insulation / generic
        _draw_speckle(img, draw, size, base, rng)

    img = img.filter(ImageFilter.SMOOTH_MORE)
    img.save(dest, "PNG")


def _shift(color, d):
    return tuple(max(0, min(255, c + d)) for c in color)


def _draw_wood(draw, size, base, rng):
    for y in range(0, size, 6):
        d = rng.randint(-25, 25)
        draw.rectangle([0, y, size, y + 6], fill=_shift(base, d))
    for _ in range(14):  # darker grain lines
        y = rng.randint(0, size)
        draw.line([(0, y), (size, y + rng.randint(-8, 8))],
                  fill=_shift(base, -45), width=rng.randint(1, 3))


def _draw_brushed_metal(draw, size, base, rng):
    for x in range(size):
        d = rng.randint(-18, 18)
        draw.line([(x, 0), (x, size)], fill=_shift(base, d))
    # subtle diagonal highlight
    for i in range(-size, size, 40):
        draw.line([(i, 0), (i + size, size)], fill=_shift(base, 30), width=2)


def _draw_brick(draw, size, base, rng):
    bw, bh = 80, 30
    mortar = (210, 205, 198)
    for row, y in enumerate(range(0, size, bh)):
        offset = (bw // 2) if row % 2 else 0
        for x in range(-bw, size, bw):
            x0 = x + offset
            draw.rectangle([x0, y, x0 + bw - 4, y + bh - 4],
                           fill=_shift(base, rng.randint(-20, 20)))
        draw.line([(0, y), (size, y)], fill=mortar, width=4)


def _draw_glass(draw, size, base, rng):
    for y in range(size):
        t = y / size
        draw.line([(0, y), (size, y)], fill=_shift(base, int(40 * (0.5 - t))))
    for x in range(0, size, 128):  # mullions
        draw.line([(x, 0), (x, size)], fill=(90, 110, 120), width=6)
    draw.line([(0, 0), (size, size)], fill=(255, 255, 255), width=10)


def _draw_speckle(img, draw, size, base, rng):
    px = img.load()
    for x in range(size):
        for y in range(size):
            if rng.random() < 0.12:
                px[x, y] = _shift(base, rng.randint(-22, 22))

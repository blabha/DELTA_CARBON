"""
Import a texture image (e.g. downloaded free from architextures.org for
educational use) into the SURROUND material library.

Usage:
    python add_texture.py <material> <path-to-color-image> [normal-image] [orm-image]

Examples:
    python add_texture.py concrete  Downloads/artx-concrete.png
    python add_texture.py brick     Downloads/brick_color.png  Downloads/brick_normal.png

The colour image is required; normal/ORM are optional (sensible defaults are
generated). The material name should match a category used in the comparative
table (concrete, wood, timber, steel, brick, stone, marble, tile, plaster,
terracotta, corten, green_roof, glass, ...). After importing, just re-run
run_stage4.py — the renderer picks it up automatically.
"""

import sys
from pathlib import Path

from PIL import Image

LIB = Path(__file__).parent / "assets" / "textures" / "lib"


def add(material: str, color: str, normal: str | None = None, orm: str | None = None):
    folder = LIB / material.lower()
    folder.mkdir(parents=True, exist_ok=True)

    img = Image.open(color).convert("RGB")
    img.save(folder / "Color.jpg", quality=92)
    size = img.size

    if normal:
        Image.open(normal).convert("RGB").resize(size).save(folder / "Normal.jpg", quality=92)
    elif not (folder / "Normal.jpg").exists():
        Image.new("RGB", size, (128, 128, 255)).save(folder / "Normal.jpg")  # flat normal

    if orm:
        Image.open(orm).convert("RGB").resize(size).save(folder / "ORM.jpg", quality=92)
    elif not (folder / "ORM.jpg").exists():
        # AO=white, roughness=mid, metalness=black
        Image.merge("RGB", [Image.new("L", size, 255),
                            Image.new("L", size, 150),
                            Image.new("L", size, 0)]).save(folder / "ORM.jpg", quality=92)

    print(f"Imported '{material}' -> {folder}")
    print("Re-run: python run_stage4.py")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    add(sys.argv[1], sys.argv[2],
        sys.argv[3] if len(sys.argv) > 3 else None,
        sys.argv[4] if len(sys.argv) > 4 else None)

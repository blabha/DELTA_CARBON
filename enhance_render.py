"""
AI photoreal polish for the user-model render.

Pipeline:
  1. render a CLEAN hero (no titles/legend) so the AI doesn't try to redraw text
  2. image-to-image enhance it with Gemini (geometry/materials preserved)
  3. re-stamp the Material Passport on top -> carbon data stays crisp & accurate

Usage:
  python enhance_render.py                      # render clean hero + enhance
  python enhance_render.py output/usermodel_hero.png   # enhance an existing image

Needs GEMINI_API_KEY in .env (already configured here). Output:
  output/usermodel_hero_ai.png   (enhanced + passport)
  output/usermodel_hero_clean.png (clean render fed to the AI)
"""
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from PIL import Image

from pipeline import vtk_render as VR
from pipeline.enhance import enhance_image
import render_usermodel as RU

HERE = Path(__file__).parent
OUT = HERE / "output"


def main():
    legend = None
    clean = OUT / "usermodel_hero_clean.png"

    if len(sys.argv) > 1:                         # enhance an existing image as-is
        clean = Path(sys.argv[1])
    else:                                         # render a fresh clean hero
        bounds, subs, gm, legend, glass = RU.prepare()
        env = RU.get_environment("qwantani_noon_puresky")
        RU.render(subs, gm, legend, glass, bounds, env, 12, -58, str(clean),
                  (1600, 2000), overlay=False)

    # provider: --openai or PROVIDER=openai (default gemini)
    provider = "openai" if "--openai" in sys.argv else os.getenv("PROVIDER", "gemini")
    ai = OUT / "usermodel_hero_ai.png"
    print(f"enhancing via {provider} (image-to-image)...")
    try:
        from pipeline.enhance import QuotaError, enhance
        enhance(clean, ai, provider=provider)
    except QuotaError as e:
        print("\n[!] " + str(e))
        print("    The clean render is ready at:", clean)
        print("    Enable billing, then re-run: python enhance_render.py")
        return

    # re-stamp titles + passport so the carbon data is exact and legible
    if legend is not None:
        img = Image.open(ai).convert("RGB")
        img = VR._add_titles(img, "Massing Model 2 - SURROUND Material Study (AI polish)",
                             RU.SITE)
        img = VR._add_legend(img, legend)
        img.save(ai)
    print("saved", ai)


if __name__ == "__main__":
    main()

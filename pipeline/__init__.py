"""
Surround Stage 4 — Visualisation pipeline (Rim).

Takes the Material Comparative Table from Stage 3 (Bhavana) and, per surface:
  1. selects the best material choice,
  2. fetches its texture (scrape manufacturer site -> fallback texture library),
  3. applies the texture to the massing model,
and once all materials are applied, renders the building with the Gemini API
(falling back to an offline mock render when no API key is configured).
"""

__all__ = [
    "models",
    "select_materials",
    "texture_scraper",
    "apply_texture",
    "gemini_render",
]

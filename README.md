# Surround — Stage 4: Visualisation (Rim)

The **Visualisation** stage of the SURROUND Upfront-Carbon pipeline (the red
"Rim" box in the system diagram). It takes the **Material Comparative Table**
produced by Stage 3 (Bhavana) and turns the winning materials into a textured,
photorealistic visualisation of the building.

```
Stage 3 (Bhavana)              Stage 4 (this repo — Rim)
comparative_table.csv  ──►  1. Select best choice per surface
                            2. Get material texture  (scrape → fallback library)
                            3. Apply texture to massing model      ⟲ loop
                            4. (when all materials applied)
                            5. Visualisation using Gemini API  →  final_render.png
```

## What it does

1. **Select best choice** — reads `comparative_table.csv` and keeps the top-ranked
   material for each surface (roof, wall, floor).
2. **Get material texture** — tries to scrape a texture image from the
   manufacturer's website; if there's no confirmed URL or the fetch fails, it
   generates a deterministic, category-appropriate texture (wood / concrete /
   steel / brick / glass / …). Never fatal.
3. **Apply texture to model** — warps each texture onto the matching face of a
   massing model and composites a textured preview.
4. **Visualisation (Gemini)** — sends the textured massing + a material prompt to
   the Gemini image API for a photorealistic render. With no `GEMINI_API_KEY`,
   it produces an annotated **mock render** instead (offline mode), mirroring
   Stage 3's offline behaviour.

## Run

```bash
pip install -r requirements.txt
python run_visualisation.py
```

Outputs (in `output/`):
- `textured_massing.png` — massing with materials applied
- `final_render.png` — final visualisation (Gemini or mock)
- `visualisation_manifest.json` — surfaces, materials, carbon, texture sources

Config is optional via a `.env` file (see `.env.example`): `GEMINI_API_KEY`,
`GEMINI_MODEL`, `COMPARATIVE_TABLE`.

## Status / placeholders

- **Massing model:** Stage 2's real mesh (OBJ/glTF) isn't wired in yet, so a
  placeholder axonometric box is rendered. Replace `build_massing_placeholder`
  and the `FACES` geometry in `pipeline/apply_texture.py` with a real renderer
  (e.g. trimesh/pyrender) when the mesh is available — the rest of the pipeline
  is unaffected.
- **Texture scraping:** add confirmed manufacturer URLs to `MANUFACTURER_URLS`
  in `pipeline/texture_scraper.py` to enable live scraping; until then the
  procedural fallback is used.
- **Gemini SDK / bs4:** both optional. Without them the pipeline still runs
  (mock render + regex scraping).

## Layout

```
SURROUND_UPFRONT-CARBON-Rim/
├── run_visualisation.py        Entry point — wires all steps
├── pipeline/
│   ├── select_materials.py     Step 1: read comparative table → best per surface
│   ├── texture_scraper.py      Step 2: scrape texture → procedural fallback
│   ├── apply_texture.py        Step 3: warp textures onto massing faces
│   ├── gemini_render.py        Step 5: Gemini render + offline mock
│   └── models.py               Shared dataclasses
├── assets/textures/            Resolved textures (per surface)
├── massing/                    Placeholder massing image
├── output/                     Textured massing, final render, manifest
├── requirements.txt
└── .env.example
```

# Process Walkthrough — Stage 4 (Visualisation) · Rim

*A plain-language summary of what was built and how it was published, written to
explain the work to the professor.*

---

## 1. Where this sits in the team project

**SURROUND** is an AI-driven tool that estimates a building's **upfront embodied
carbon (life-cycle A1–A3)** at the **massing stage** — before the design is
frozen — and helps the architect choose lower-carbon materials using real EPD
(Environmental Product Declaration) data and neighbourhood context (22@ Poblenou,
Barcelona). The pipeline is split into four stages, one per teammate:

| Stage | Owner | Job | Hands off |
|---|---|---|---|
| 1 — Site & LCA setup | Martina | Coordinates → plot area → baseline carbon target | building type, target |
| 2 — Massing analysis | Rashi | Recognise wall/floor/roof, export tagged geometry | **OBJ/JSON** |
| 3 — Material carbon | Bhavana | EPD search → carbon per surface → best options | **comparative_table.csv** |
| **4 — Visualisation** | **Rim (me)** | Put the chosen materials on the model and render it | textured model + render |

**My stage (Stage 4) is the last one** — it makes the carbon decision *visible*
by showing the building "wearing" the chosen materials.

---

## 2. What Stage 4 actually does

It takes two inputs from upstream — Bhavana's `comparative_table.csv` (*what*
material wins on each surface) and Rashi's massing OBJ (*the shape*) — and runs a
loop, once per surface:

1. **Select best choice** — read the comparative table, keep the top-ranked
   material for each surface (roof / wall / floor / glass).
2. **Get material texture** — pull a real CC0 PBR texture (Poly Haven 2K, with
   normal + ORM maps; ambientCG fallback) matched to the EPD material category.
   A manufacturer-site scrape is attempted first; there is also a drop-in path
   for Architextures via `add_texture.py`.
3. **Apply texture to model** — parse the OBJ, classify each face into
   glass / roof / wall / floor (glass is read from the OBJ material name, e.g.
   `Translucent_Glass_Gray`), and map each material onto its faces.
4. **Visualise** — once all materials are applied, produce a **physically-based
   render** (VTK: PBR materials + HDR image-based lighting + shadows + filmic
   tone mapping), with a **day** and an **evening** version (reflective sky-glass
   by day, warm lit windows at dusk). It also exports an **interactive 3D**
   `massing.glb` plus an offline web viewer (orbit / pan / zoom).

An optional **AI photoreal polish** (Gemini/Stability *image-to-image*) is a paid
add-on. Free *text-to-image* was deliberately dropped because it invents a
generic building instead of rendering *our* massing — off-mission.

### Build status (all the core pieces work)

| Step | Status |
|---|---|
| Read comparative table → best per surface | ✅ working |
| CC0 PBR material library (~15 materials auto-mapped) | ✅ working |
| Load + classify massing OBJ faces | ✅ working |
| Faithful PBR render (day / evening, lit windows) | ✅ working |
| Interactive 3D output (GLB + web viewer) | ✅ working |
| AI photoreal polish | 🟡 optional, paid only |

**Decoupling matters:** every step runs on **sample/placeholder inputs**, so my
stage was developed and tested independently and only needs to be "wired" to the
real upstream OBJ and CSV when they land.

---

## 3. Key files (so I can point to them live)

```
SURROUND_UPFRONT-CARBON-Rim/
├── run_visualisation.py / run_stage4.py   Entry points — wire all steps
├── pipeline/
│   ├── select_materials.py    Step 1: comparative table → best per surface
│   ├── texture_scraper.py     Step 2: scrape texture → procedural fallback
│   ├── apply_texture.py       Step 3: warp textures onto massing faces
│   ├── gemini_render.py       Optional AI polish + offline mock
│   └── models.py              Shared dataclasses
├── render_final.py            Day + evening "hero" renders
├── add_texture.py             Texture import (Architextures drop-in)
├── assets/ · massing/ · output/   Textures, massing image, renders + manifest
├── requirements.txt · .env.example
└── SURROUND_SYSTEM_ARCHITECTURE.md   Full system write-up
```

---

## 4. How the work was published to GitHub (today)

The folder was local-only; the goal was to publish **just my Stage-4 work** to my
own branch on the shared team repository
[`blabha/SURROUND_UPFRONT-CARBON`](https://github.com/blabha/SURROUND_UPFRONT-CARBON),
**branch `Rim`** — without touching teammates' folders and without leaking secrets.

The steps taken:

1. **Scoped the push** to the `SURROUND_UPFRONT-CARBON-Rim` folder only (the
   parent folder also held Martina's and Bhavana's work — those were excluded).
2. **Security scan.** Found real API keys in a `.env` file
   (`GEMINI_API_KEY`, `HF_TOKEN`). These were added to `.gitignore` so they were
   **never committed or pushed**. The safe `.env.example` (empty placeholders)
   *was* pushed instead — the standard convention.
3. **Handled an oversized file.** The massing model
   `Massing-Model 7 version.obj` is **345 MB**, over GitHub's 100 MB per-file
   limit, so it was excluded via `.gitignore` (the small `.mtl` material file was
   kept). It stays on my machine; nothing over 100 MB was pushed.
4. **Ignored junk** — `__pycache__/`, caches, OS files.
5. **Committed** the 131 source/asset files and **merged** the one pre-existing
   commit already on the remote `Rim` branch (a placeholder README) instead of
   force-overwriting it — so no existing work was destroyed.
6. **Pushed** to `origin/Rim`. ✅

**Result:** the full Stage-4 pipeline (code, textures, sample data, renders,
docs) is now on the `Rim` branch, the model file and secret keys are safely
excluded, and the team's history was preserved.

> Note: because the keys lived in plaintext locally, the safe practice going
> forward is to **rotate** the Gemini and Hugging Face keys.

---

## 5. One-sentence summary for the prof

> *"My stage takes the winning low-carbon materials from Bhavana's comparative
> table and the massing model from Rashi, maps real PBR textures onto each
> classified surface, and produces a faithful physically-based day/evening render
> plus an interactive 3D viewer — making the embodied-carbon decision a visible
> design outcome. It's now published to my `Rim` branch on the team repo, with
> the 345 MB model and the API keys safely kept out of version control."*

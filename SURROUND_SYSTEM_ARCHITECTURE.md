# SURROUND — System Architecture & Project Overview

> Circular material matching · Embodied-carbon tool · 22@ Poblenou, Barcelona
> Team: **Martina · Rashi · Bhavana · Rim**
> This document is written from **Rim's** seat (Stage 4 — Visualisation) but
> describes the whole system so the parts can be connected later.

---

## 1. The Idea in One Paragraph

SURROUND is an AI-driven tool that estimates the **upfront embodied carbon
(life-cycle stages A1–A3)** of a building **at the massing stage** — before the
design is fixed — and helps the architect pick lower-carbon materials using
real EPD (Environmental Product Declaration) data and neighbourhood building
context. It then **shows the building wearing those chosen materials** so the
carbon decision becomes a visible design decision.

---

## 2. Research Framing

| | |
|---|---|
| **Research question** | How can AI-driven upfront carbon assessment reduce embodied carbon in 22@ renovation? |
| **Framing** | ~70% of sustainability impact is locked in at the massing stage — material choices must be assessed *before* the design is frozen. |
| **Total aim** | Deliver a tool that estimates upfront carbon (A1–A3) at massing stage using neighbourhood building data. |
| **Context** | 22@ Poblenou, Barcelona · 1,691 buildings mapped · ~207 kg CO₂e/m² district average. |
| **Problem** | No early-stage carbon tool exists. Tally = mid-stage / Revit only · One-Click LCA = late stage · EC3 = database only, no design. |
| **Motivation** | Embodied carbon ≈ 11% of global emissions; ~50% of a building's lifetime carbon is locked in before occupation. |
| **Gap** | No accessible, location-aware tool estimates upfront carbon A1–A3 at massing stage using neighbourhood data. |

---

## 3. The Four Stages (Swimlanes)

The system is a left-to-right pipeline. Each teammate owns one lane. Boxes below
mirror the system diagram.

### Stage 1 — Site & LCA Setup · **Martina** *(green)*
- **Inputs:** Building Type · site coordinates · plot boundary
- **Steps:**
  - Enter coordinates → **Get surrounding model** (neighbourhood context)
  - Select plot boundary → **Calculate plot area**
  - Building Type + area → **LCA Prediction model** (carbon target by type & area)
- **Output:** building type, plot area, and a baseline carbon prediction / target

### Stage 2 — Massing Model Analysis · **Rashi** *(purple)*
- **Inputs:** the 3D massing model (uploaded)
- **Steps:**
  - Upload massing model → **Calculate building area**
  - **Wall / Floor / Roof recogniser** → for each surface compute:
    1. individual wall surface, 2. individual wall volume,
    3. individual roof surface, 4. individual roof volume
  - **OBJ → JSON** (geometry exported with per-surface tags)
  - Select surface → **Get Area / Volume**
- **Output:** per-surface **area & volume**, plus the tagged geometry (**OBJ/JSON**)

### Stage 3 — Material Carbon Analysis · **Bhavana** *(blue)*
- **Inputs:** surface type + area/volume (from Stage 2), a material choice (e.g. "Wood")
- **Steps:**
  - **EPD API** — search by *location/country + search word*, download EPD PDFs
  - **PDF reader → CSV** — extract: product name, embodied carbon (per kg/unit),
    company, location, notes
  - **Rule-based unit parser** — per kg (concrete, steel…) vs per unit (tiles, windows…)
  - **Weights** — compute embodied carbon for the surface; keep **top 5** options by
    *closest location* + *lowest embodied carbon*
  - **Material Comparative Table** — best option(s) per surface
  - When all materials applied → **Generate Report** (carbon passport PDF)
- **Output:** `comparative_table.csv` + carbon report

### Stage 4 — Visualisation · **Rim (me)** *(red — runs as a LOOP per surface)*
- **Inputs:** the Material Comparative Table (Stage 3) + the massing model (Stage 2)
- **Steps (loop per surface):**
  1. **Select best choice** — winning material for the surface (from the table)
  2. **Get material texture** — from the bundled **CC0 PBR library** (Poly Haven,
     2K, with normal + ORM maps; ambientCG fallback), keyed to the EPD material
     category. Manufacturer-site scrape attempted first; Architextures drop-in
     supported via `add_texture.py`.
  3. **Apply material texture to model** — load + classify the massing faces into
     **glass / roof / wall / floor** (glass read from the OBJ material name, e.g.
     `Translucent_Glass_Gray`), then map each material onto its faces.
  - …loop until **all materials applied**
  4. **Visualisation** — a **faithful, physically-based render** (VTK: PBR
     materials + HDR image-based lighting + shadows + filmic tone mapping), with
     reflective sky-glass by day or warm lit windows at dusk. Also exports an
     interactive textured **GLB + web viewer**.
- **Output:** the faithful render(s) (`output/final_day.png`, `final_evening.png`)
  + interactive `massing.glb` / viewer.
- **Note:** a *photoreal AI* polish (Gemini/Stability **image-to-image**) is an
  optional paid add-on. Free *text-to-image* was dropped — it produces a generic
  building, not your massing, so it's off-mission.

---

## 4. Data Contracts (how the lanes connect)

These are the only hand-offs that matter. Each can be built and tested
independently against a sample file, then wired to the real upstream later.

| From → To | Hand-off | Shape |
|---|---|---|
| Rashi → Bhavana | per-surface area/volume | surface_id, surface_type, area_m², volume_m³ |
| Rashi → **Rim** | massing geometry | **OBJ/JSON** (surfaces tagged wall/floor/roof) |
| Bhavana → **Rim** | Material Comparative Table | `comparative_table.csv` (best material per surface: product, manufacturer, location, carbon, area) |
| Martina → Bhavana | building type, target | use_type, plot area, carbon benchmark |
| **Rim** → output | textured model + render | `massing.glb`, viewer, final render |

**Rim depends on two upstream inputs:**
1. **Bhavana's `comparative_table.csv`** — *what* material goes on each surface.
2. **Rashi's massing OBJ** — *the shape* to put the materials on.

Everything in Stage 4 can run on **sample/placeholder versions** of these two
until the real ones are ready.

---

## 5. Stage 4 (Rim) — Build Status

| Step | Status | Notes |
|---|---|---|
| Select best choice (read comparative table) | ✅ working | reads the `comparative_table.csv` contract (own sample, decoupled) |
| Material library (CC0 PBR) | ✅ working | Poly Haven 2K (color+normal+ORM) + ambientCG fallback; ~15 materials auto-mapped from EPD category; Architextures via `add_texture.py` |
| Load + classify massing | ✅ working | OBJ parsed; faces → glass/roof/wall/floor (glass from material name) |
| Faithful PBR render | ✅ working | VTK PBR + HDR IBL + shadows + tone mapping; day / evening; lit windows |
| Interactive 3D output (GLB + web viewer) | ✅ working | orbit / pan / zoom, offline |
| AI photoreal polish (optional) | 🟡 paid only | image-to-image needs a paid provider; free text-to-image dropped (off-mission) |

**Placeholders to remove as upstreams land:**
- Engel House model → Rashi's real OBJ/JSON (loader already handles arbitrary OBJ + its materials)
- Bundled CC0 textures → manufacturer / Architextures textures (drop-in ready)

**Key scripts:** `run_stage4.py` (main render), `render_final.py` (day+evening
heroes), `render_engel.py` / `render_compare.py` / `render_materials.py`
(angle / sky / material studies), `add_texture.py` (texture import).

---

## 6. Pipeline Diagram (Stage 4 focus)

```
Rashi (OBJ massing) ─────────────┐
                                 ▼
Bhavana (comparative_table.csv) ─► [Select best] ─► [Get texture] ─► [Apply to model]
                                        ▲_______________ loop per surface ______________│
                                                                                         ▼
                                                              [all applied] ─► [3D view] ─► [Gemini render]
```

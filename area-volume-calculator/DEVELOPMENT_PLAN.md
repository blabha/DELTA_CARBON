# Development Plan — Rashi Zone

## Goal
Build the geometry processing module that takes a massing model (OBJ), classifies surfaces, calculates area/volume, and outputs structured JSON.

---

## Phase 1 — OBJ Parsing
**Goal:** Load an OBJ file and extract raw face/vertex data.

- [ ] Parse vertices (`v`) and faces (`f`) from OBJ
- [ ] Handle both triangulated and quad faces
- [ ] Return a clean in-memory mesh representation
- [ ] Unit test: load a simple cube OBJ and verify vertex/face counts

---

## Phase 2 — Surface Classification (Wall / Floor / Roof Recogniser)
**Goal:** Classify each face group by orientation using face normals.

- [ ] Compute per-face normal vectors
- [ ] Apply classification rules:
  - Normal dot `(0,0,1)` > 0.9 → **roof**
  - Normal dot `(0,0,-1)` > 0.9 → **floor**
  - Otherwise → **wall**
- [ ] Group contiguous faces of the same type into named surfaces
- [ ] Unit test: verify normals on a cube (top=roof, bottom=floor, sides=wall)

---

## Phase 3 — Area & Volume Calculation ✅
**Goal:** Calculate area and volume for each classified surface.

- [x] Compute polygon area using cross product (triangulated faces)
- [x] Volume strategy:
  - `wall / floor / roof` (single-skin Rhino surfaces) → `area × 0.2 m` assumed thickness
  - `railing / window / frame` (modelled as 3D solids) → divergence theorem
- [x] Accumulate per-surface and total values
- [x] `assumed_thickness_m` field added to JSON output for wall/floor/roof entries
- [x] Thickness defaults in `geometry/calculator.py :: THICKNESS_M` — edit there to change

---

## Phase 4 — OBJ → JSON Export
**Goal:** Serialise results to the defined JSON schema.

- [ ] Build surface dicts with id, type, area_m2, volume_m3, vertices
- [ ] Compute totals block
- [ ] Write to `.json` output file
- [ ] Integration test: OBJ in → JSON out → validate schema

---

## Phase 5 — CLI Entry Point
**Goal:** Provide a usable command-line interface.

- [ ] `--input` flag for OBJ path
- [ ] `--output` flag for JSON path (default: `output.json`)
- [ ] `--verbose` flag for debug logging
- [ ] Graceful error messages for bad input files

---

## Phase 6 — Validation & Polish
- [ ] Test with real massing model OBJs (simple box, L-shape, pitched roof)
- [ ] Edge cases: non-manifold geometry, disconnected shells, very small faces
- [ ] Performance check on models with >10,000 faces

---

## Out of Scope (handled by other pipeline zones)
- LCA prediction model (Martina zone)
- EPD API lookup and PDF parsing (blue zone)
- Material texture application and Gemini visualisation (red zone)
- Surrounding site model retrieval

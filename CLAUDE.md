# CLAUDE.md — SURROUND_UPFRONT-CARBON

## Project Overview
A pipeline tool for **upfront embodied carbon estimation** of buildings.
This codebase implements the **"Rashi" zone** of the full pipeline:
- Upload a massing model (OBJ)
- Recognise and classify surfaces: wall / floor / roof
- Calculate per-surface area and volume
- Export structured JSON for downstream carbon calculation

## Architecture
```
massing_model/          # OBJ upload and parsing utilities
surface_recogniser/     # Geometry classification (wall / floor / roof)
geometry/               # Area and volume calculation helpers
export/                 # OBJ → JSON serialisation
tests/                  # Unit and integration tests
main.py                 # CLI entry point
```

## Key Concepts
- Input: `.obj` massing model file (single-shell or multi-shell)
- Surface classification uses the Rhino layer name first (keyword match), falls back to face normals
- **Volume method:**
  - `wall`, `floor`, `roof` → `area × assumed_thickness` (default 0.2 m). These are single-skin Rhino surfaces with no geometric depth.
  - `railing`, `window`, `frame`, etc. → divergence theorem (these are modelled as 3D closed solids in Rhino).
- Thickness defaults live in `geometry/calculator.py :: THICKNESS_M`
- Output JSON schema:
  ```json
  {
    "surfaces": [
      {
        "id": "wall_0",
        "type": "wall | floor | roof",
        "area_m2": 0.0,
        "volume_m3": 0.0,
        "vertices": [[x, y, z], ...]
      }
    ],
    "totals": {
      "wall_area_m2": 0.0,
      "floor_area_m2": 0.0,
      "roof_area_m2": 0.0,
      "wall_volume_m3": 0.0,
      "roof_volume_m3": 0.0
    }
  }
  ```

## Development Environment
- Python 3.11+
- Virtual environment: `venv/` (not committed)
- Activate: `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Mac/Linux)
- Install: `pip install -r requirements.txt`

## Running
```bash
python main.py --input path/to/model.obj --output output.json
```

## Testing
```bash
pytest tests/
```

## Conventions
- Use `numpy` for all vector/matrix math
- Surface normal threshold: dot product with up-vector > 0.9 → roof, < -0.9 → floor, else wall
- All units: metres, metres², metres³
- JSON output always uses snake_case keys

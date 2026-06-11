"""
Step 1 — Select best choice.

Reads the Material Comparative Table produced by Stage 3 (Bhavana) and returns
the winning material per surface. The table already ranks options per surface,
so we keep Rank == 1 rows (one per surface).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .models import SelectedMaterial

# Column names as written by Stage 3 (output/comparative_table.csv).
COL_SURFACE_ID = "Surface ID"
COL_SURFACE_TYPE = "Surface Type"
COL_AREA = "Area (m²)"
COL_CATEGORY = "Material Category"
COL_PRODUCT = "Product Name"
COL_MANUFACTURER = "Manufacturer"
COL_LOCATION = "Location"
COL_COUNTRY = "Country"
COL_EPD = "EPD Number"
COL_TOTAL_CO2 = "Total CO₂e (kg)"
COL_PER_M2 = "CO₂e per m² (kg/m²)"
COL_RANK = "Rank"


def load_selected_materials(csv_path: str | Path) -> list[SelectedMaterial]:
    """Load the comparative table and return the top pick for each surface."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Comparative table not found: {csv_path}\n"
            "Run Stage 3 (Bhavana's pipeline) first to produce "
            "output/comparative_table.csv."
        )

    df = pd.read_csv(csv_path)

    if COL_RANK in df.columns:
        df = df[df[COL_RANK] == df.groupby(COL_SURFACE_ID)[COL_RANK].transform("min")]
    # Otherwise assume the table already holds one row per surface.

    selected: list[SelectedMaterial] = []
    for _, row in df.iterrows():
        selected.append(
            SelectedMaterial(
                surface_id=str(row[COL_SURFACE_ID]),
                surface_type=str(row[COL_SURFACE_TYPE]),
                material_category=str(row[COL_CATEGORY]).lower(),
                product_name=str(row[COL_PRODUCT]),
                manufacturer=str(row[COL_MANUFACTURER]),
                location=str(row.get(COL_LOCATION, "")),
                country=str(row.get(COL_COUNTRY, "")),
                area_m2=float(row[COL_AREA]),
                total_co2e_kg=float(row[COL_TOTAL_CO2]),
                co2e_per_m2=float(row[COL_PER_M2]),
                epd_number=str(row.get(COL_EPD, "")),
            )
        )

    # Stable surface order for deterministic rendering.
    order = {"floor": 0, "wall": 1, "roof": 2}
    selected.sort(key=lambda m: order.get(m.surface_type.lower(), 99))
    return selected

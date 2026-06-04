"""
Step 6 — Material Comparative Table Generator
Aggregates top-ranked results across all building surfaces into a single
structured table. Triggered once all surfaces have been processed.
"""

from dataclasses import dataclass

import pandas as pd

from pipeline.ranking import RankedResult


@dataclass
class SurfaceSummary:
    """Top-ranked result chosen for one surface (rank 1 by default)."""
    surface_id: str
    surface_type: str
    area_m2: float
    material_category: str
    chosen_product: str
    company: str
    location: str
    country: str
    epd_number: str
    total_co2e_kg: float
    co2e_per_m2: float
    rank: int
    distance_km: float | None


def build_comparative_table(
    surface_rankings: dict[str, list[RankedResult]],
    surface_types: dict[str, str] | None = None,
) -> pd.DataFrame:
    """
    Build the Material Comparative Table from per-surface rankings.

    Args:
        surface_rankings: Dict mapping surface_id → list[RankedResult] (from ranking.py)
        surface_types:    Optional dict mapping surface_id → surface_type label
                          e.g. {"roof_01": "Roof", "wall_north": "Wall"}

    Returns:
        DataFrame with one row per surface showing the top-ranked material choice
        and its carbon performance.
    """
    rows = []
    for surface_id, ranked in surface_rankings.items():
        if not ranked:
            continue
        best = ranked[0]
        cr = best.carbon_result
        surface_type = (surface_types or {}).get(surface_id, cr.surface_id.split("_")[0].title())
        rows.append({
            "Surface ID": surface_id,
            "Surface Type": surface_type,
            "Area (m²)": cr.area_m2,
            "Material Category": cr.material_category,
            "Product Name": cr.product_name,
            "Manufacturer": cr.company,
            "Location": cr.location,
            "Country": cr.country,
            "EPD Number": cr.epd_number,
            "Total CO₂e (kg)": cr.total_co2e_kg,
            "CO₂e per m² (kg/m²)": round(cr.total_co2e_kg / cr.area_m2, 2) if cr.area_m2 else None,
            "Rank": best.rank,
            "Distance (km)": round(best.distance_km, 1) if best.distance_km else None,
            "Geo Score": best.geo_score,
            "Carbon Score": best.carbon_score,
            "Combined Score": best.combined_score,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Surface ID").reset_index(drop=True)
    return df


def summary_stats(df: pd.DataFrame) -> dict:
    """
    Compute project-level carbon summary from the comparative table.
    Returns totals and intensity metrics used in the report.
    """
    if df.empty:
        return {}

    total_co2e = df["Total CO₂e (kg)"].sum()
    total_area = df["Area (m²)"].sum()
    intensity = total_co2e / total_area if total_area else 0.0

    # Carbon split by surface type
    split = (
        df.groupby("Surface Type")["Total CO₂e (kg)"]
        .sum()
        .sort_values(ascending=False)
        .to_dict()
    )

    # Industry benchmark from the Surround project context
    benchmark_kg_m2 = 240.0
    vs_benchmark_pct = ((intensity - benchmark_kg_m2) / benchmark_kg_m2) * 100

    return {
        "total_co2e_kg": round(total_co2e, 1),
        "total_co2e_t": round(total_co2e / 1000, 2),
        "total_area_m2": round(total_area, 1),
        "intensity_kg_m2": round(intensity, 1),
        "benchmark_kg_m2": benchmark_kg_m2,
        "vs_benchmark_pct": round(vs_benchmark_pct, 1),
        "carbon_split_by_type": split,
        "n_surfaces": len(df),
    }


def export_table(df: pd.DataFrame, output_path: str) -> None:
    """Save the comparative table to CSV."""
    df.to_csv(output_path, index=False)

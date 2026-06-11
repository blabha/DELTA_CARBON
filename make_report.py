"""
Generate a corrected carbon report from Stage 3's comparative table.

Reads Bhavana's output/comparative_table.csv, recomputes the summary stats it
needs, and renders a fixed PDF (Unicode glyphs + non-overlapping table) into
this folder's output/. Bhavana's own code is not modified.

Usage:
    python make_report.py
"""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from pipeline.report_fixed import generate_report

load_dotenv()

PROJECT_NAME = "22@ Poblenou Residential Block"
SITE_LOCATION = "22@ Poblenou, Barcelona, Spain"
BUILDING_TYPE = "Residential"
BENCHMARK_KG_M2 = 240.0

HERE = Path(__file__).parent
DEFAULT_TABLE = (
    HERE.parent
    / "SURROUND_UPFRONT-CARBON-bhavana (1)"
    / "SURROUND_UPFRONT-CARBON-bhavana"
    / "output"
    / "comparative_table.csv"
)
COMPARATIVE_TABLE = Path(os.getenv("COMPARATIVE_TABLE", str(DEFAULT_TABLE)))
OUTPUT_DIR = HERE / "output"


def compute_stats(df: pd.DataFrame) -> dict:
    """Recreate the summary stats the report needs, straight from the table."""
    total_co2e_kg = float(df["Total CO₂e (kg)"].sum())
    total_area = float(df["Area (m²)"].sum()) or 1.0
    intensity = total_co2e_kg / total_area
    split = (
        df.groupby("Surface Type")["Total CO₂e (kg)"].sum()
        .sort_values(ascending=False).to_dict()
    )
    return {
        "total_co2e_kg": total_co2e_kg,
        "total_co2e_t": round(total_co2e_kg / 1000, 2),
        "intensity_kg_m2": round(intensity, 1),
        "benchmark_kg_m2": BENCHMARK_KG_M2,
        "vs_benchmark_pct": round((intensity - BENCHMARK_KG_M2) / BENCHMARK_KG_M2 * 100, 1),
        "carbon_split_by_type": split,
    }


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    if not COMPARATIVE_TABLE.exists():
        raise SystemExit(f"Comparative table not found: {COMPARATIVE_TABLE}")

    df = pd.read_csv(COMPARATIVE_TABLE)
    stats = compute_stats(df)

    out_path = OUTPUT_DIR / "carbon_report_fixed.pdf"
    generate_report(
        df=df, stats=stats, output_path=out_path,
        project_name=PROJECT_NAME, site_location=SITE_LOCATION,
        building_type=BUILDING_TYPE,
    )
    print(f"Fixed report -> {out_path}")
    print(f"  Total CO2e:   {stats['total_co2e_t']} t")
    print(f"  Intensity:    {stats['intensity_kg_m2']} kg/m2")
    print(f"  vs Benchmark: {stats['vs_benchmark_pct']:+.1f}%")


if __name__ == "__main__":
    main()

import argparse
from pathlib import Path
from massing_model.parser import parse_obj
from surface_recogniser.classifier import classify_groups
from export.json_export import build_report, export_json


def main():
    parser = argparse.ArgumentParser(
        description="Calculate surface areas and volumes from an OBJ massing model."
    )
    parser.add_argument("--input", required=True, help="Path to .obj file")
    parser.add_argument("--output", default="output.json", help="Path for output .json (default: output.json)")
    parser.add_argument("--unit", choices=["m", "mm", "cm"], default="m",
                        help="Unit of the OBJ model (default: m). Use mm for Rhino default exports.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {input_path}")
        return 1

    scale = {"m": 1.0, "cm": 0.01, "mm": 0.001}[args.unit]

    if args.verbose:
        print(f"Parsing {input_path}  [units: {args.unit}, scale factor: {scale}]")

    groups = parse_obj(input_path)

    if scale != 1.0:
        for g in groups.values():
            g.vertices = g.vertices * scale

    if args.verbose:
        print(f"Found {len(groups)} group(s): {list(groups.keys())}")

    surface_types = classify_groups(groups)
    report = build_report(groups, surface_types)
    export_json(report, args.output)

    col = "{:<28} {:<12} {:>12} {:>13}"
    print(f"\n{col.format('Group', 'Type', 'Area (m²)', 'Volume (m³)')}")
    print("-" * 68)
    for s in report["surfaces"]:
        print(col.format(s["id"], s["type"], f"{s['area_m2']:.4f}", f"{s['volume_m3']:.4f}"))
    print("-" * 68)
    print("\nTotals:")
    for k, v in report["totals"].items():
        print(f"  {k}: {v:.4f}")
    print(f"\nOutput written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

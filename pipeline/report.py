"""
Step 7 — Report Generator
Produces a PDF sustainability report from the comparative table and summary stats.
Includes: material passport, carbon split by element, benchmark comparison,
and top-ranked material choices per surface.
"""

from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# ── Colour palette ────────────────────────────────────────────────────────────
NAVY = colors.HexColor("#1a3a5c")
TEAL = colors.HexColor("#2a7d6f")
LIGHT_BLUE = colors.HexColor("#dce8f5")
GREEN_HIGHLIGHT = colors.HexColor("#d4edda")
AMBER = colors.HexColor("#fff3cd")
RED_LIGHT = colors.HexColor("#f8d7da")
GREY_LIGHT = colors.HexColor("#f5f5f5")
GREY_MID = colors.HexColor("#cccccc")


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("RTitle", parent=base["Title"], fontSize=22,
                                textColor=NAVY, spaceAfter=4),
        "subtitle": ParagraphStyle("RSub", parent=base["Normal"], fontSize=11,
                                   textColor=TEAL, spaceAfter=2),
        "h2": ParagraphStyle("RH2", parent=base["Heading2"], fontSize=13,
                              textColor=NAVY, spaceBefore=14, spaceAfter=5),
        "h3": ParagraphStyle("RH3", parent=base["Heading3"], fontSize=10,
                              textColor=TEAL, spaceBefore=8, spaceAfter=3),
        "body": ParagraphStyle("RBody", parent=base["Normal"], fontSize=9, leading=14),
        "small": ParagraphStyle("RSmall", parent=base["Normal"], fontSize=8,
                                textColor=colors.grey),
        "bold": ParagraphStyle("RBold", parent=base["Normal"], fontSize=9,
                               fontName="Helvetica-Bold"),
        "centre": ParagraphStyle("RCentre", parent=base["Normal"], fontSize=9,
                                 alignment=TA_CENTER),
        "big_number": ParagraphStyle("RBigNum", parent=base["Normal"], fontSize=28,
                                     fontName="Helvetica-Bold", textColor=NAVY,
                                     alignment=TA_CENTER),
        "big_label": ParagraphStyle("RBigLabel", parent=base["Normal"], fontSize=8,
                                    textColor=colors.grey, alignment=TA_CENTER),
    }


def _header_table(text: str, width: float = 17 * cm) -> Table:
    t = Table([[text]], colWidths=[width])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


def _kpi_block(value: str, label: str, styles: dict) -> list:
    return [
        Paragraph(value, styles["big_number"]),
        Paragraph(label, styles["big_label"]),
        Spacer(1, 0.2 * cm),
    ]


def generate_report(
    df: pd.DataFrame,
    stats: dict,
    output_path: str | Path,
    project_name: str = "Surround Carbon Assessment",
    site_location: str = "",
    building_type: str = "",
) -> Path:
    """
    Generate the final sustainability PDF report.

    Args:
        df:            Comparative table DataFrame from comparative_table.build_comparative_table()
        stats:         Summary stats dict from comparative_table.summary_stats()
        output_path:   Where to save the report PDF
        project_name:  Display name for the project
        site_location: Address/city of the project
        building_type: e.g. "Residential", "Commercial"

    Returns:
        Path to the generated PDF.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    s = _styles()
    story = []

    # ── Cover ─────────────────────────────────────────────────────────────────
    cover_data = [["SURROUND\nMaterial Carbon Passport"]]
    cover = Table(cover_data, colWidths=[17 * cm])
    cover.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 18),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 20),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 20),
    ]))
    story.append(cover)
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(project_name, s["title"]))
    if site_location:
        story.append(Paragraph(f"Site: {site_location}", s["subtitle"]))
    if building_type:
        story.append(Paragraph(f"Building Type: {building_type}", s["subtitle"]))
    story.append(Paragraph("Stage A1–A3 Embodied Carbon Assessment", s["subtitle"]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=1.5, color=NAVY))
    story.append(Spacer(1, 0.5 * cm))

    # ── Section 1 — KPI Passport ──────────────────────────────────────────────
    story.append(_header_table("1. Material Carbon Passport — Key Metrics"))
    story.append(Spacer(1, 0.3 * cm))

    intensity = stats.get("intensity_kg_m2", 0)
    benchmark = stats.get("benchmark_kg_m2", 240)
    vs_pct = stats.get("vs_benchmark_pct", 0)
    benchmark_colour = GREEN_HIGHLIGHT if vs_pct <= 0 else (AMBER if vs_pct <= 20 else RED_LIGHT)
    benchmark_label = "below benchmark" if vs_pct <= 0 else "above benchmark"

    kpi_data = [
        [
            Paragraph(f"{stats.get('total_co2e_t', 0):.2f} t", s["big_number"]),
            Paragraph(f"{intensity:.0f} kg/m²", s["big_number"]),
            Paragraph(f"{vs_pct:+.1f}%", s["big_number"]),
        ],
        [
            Paragraph("Total CO₂e (tonnes)", s["big_label"]),
            Paragraph("Carbon Intensity", s["big_label"]),
            Paragraph(f"vs {benchmark} kg/m² benchmark\n({benchmark_label})", s["big_label"]),
        ],
    ]
    kpi_table = Table(kpi_data, colWidths=[5.5 * cm, 5.5 * cm, 6 * cm])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BLUE),
        ("BACKGROUND", (2, 0), (2, 1), benchmark_colour),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, GREY_MID),
        ("ROUNDEDCORNERS", [4]),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 0.4 * cm))

    # ── Section 2 — Carbon Split by Element ───────────────────────────────────
    story.append(_header_table("2. Carbon Split by Building Element"))
    story.append(Spacer(1, 0.3 * cm))

    split = stats.get("carbon_split_by_type", {})
    total_co2e = stats.get("total_co2e_kg", 1)
    split_data = [["Element", "CO₂e (kg)", "CO₂e (t)", "% of Total"]]
    for element, co2e in split.items():
        pct = (co2e / total_co2e * 100) if total_co2e else 0
        split_data.append([
            element,
            f"{co2e:,.1f}",
            f"{co2e / 1000:.2f}",
            f"{pct:.1f}%",
        ])
    split_data.append(["TOTAL", f"{total_co2e:,.1f}", f"{total_co2e/1000:.2f}", "100%"])

    split_table = Table(split_data, colWidths=[5 * cm, 4 * cm, 4 * cm, 4 * cm])
    split_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), LIGHT_BLUE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [GREY_LIGHT, colors.white]),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, GREY_MID),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(split_table)
    story.append(Spacer(1, 0.5 * cm))

    # ── Section 3 — Material Comparative Table ────────────────────────────────
    story.append(PageBreak())
    story.append(_header_table("3. Material Comparative Table — Top Choice per Surface"))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        "The table below shows the highest-ranked material option for each building surface, "
        "selected by combined score (70% lowest carbon / 30% nearest supplier).",
        s["body"],
    ))
    story.append(Spacer(1, 0.3 * cm))

    if not df.empty:
        display_cols = [
            "Surface ID", "Surface Type", "Area (m²)", "Material Category",
            "Product Name", "Manufacturer", "Country",
            "Total CO₂e (kg)", "CO₂e per m² (kg/m²)", "Distance (km)",
        ]
        available = [c for c in display_cols if c in df.columns]
        col_widths = [2.5, 2, 1.8, 2.2, 3.5, 3, 1.5, 2.2, 2.5, 2]
        col_widths_cm = [w * cm for w in col_widths[:len(available)]]

        table_data = [available]
        for _, row in df.iterrows():
            table_data.append([str(row.get(c, "")) for c in available])

        mat_table = Table(table_data, colWidths=col_widths_cm, repeatRows=1)
        mat_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [GREY_LIGHT, colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.4, GREY_MID),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("WORDWRAP", (0, 0), (-1, -1), True),
        ]))
        story.append(mat_table)

    story.append(Spacer(1, 0.5 * cm))

    # ── Section 4 — Baseline vs Altered Scenario ──────────────────────────────
    story.append(_header_table("4. Baseline vs Altered Scenario"))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        "Comparison of the selected EPD-verified material set against the 22@ Poblenou "
        f"district average of 207 kg CO₂e/m² and the industry benchmark of {benchmark} kg CO₂e/m².",
        s["body"],
    ))
    story.append(Spacer(1, 0.3 * cm))

    scenario_data = [
        ["Scenario", "Intensity (kg CO₂e/m²)", "vs Benchmark"],
        ["22@ District Average", "207", f"{((207 - benchmark) / benchmark * 100):+.1f}%"],
        ["Industry Benchmark", str(benchmark), "0.0%"],
        ["This Design (EPD-verified)", f"{intensity:.1f}", f"{vs_pct:+.1f}%"],
    ]
    scen_table = Table(scenario_data, colWidths=[7 * cm, 5.5 * cm, 4.5 * cm])
    scen_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 3), (-1, 3), benchmark_colour),
        ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, 2), [GREY_LIGHT, colors.white]),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, GREY_MID),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(scen_table)
    story.append(Spacer(1, 0.5 * cm))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=GREY_MID))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        "Generated by Surround Carbon Pipeline · Stage A1–A3 only · "
        "Data sourced from EPD database (2050-materials.com) · "
        "Benchmark: 240 kg CO₂e/m² (industry standard)",
        s["small"],
    ))

    doc.build(story)
    return output_path

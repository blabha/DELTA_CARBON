"""
Fixed PDF report generator (Rim's copy).

This is a corrected version of Stage 3's report renderer. Bhavana's original
(pipeline/report.py in her folder) is left untouched. Two bugs are fixed here:

  1. Broken glyphs — the original draws with Helvetica, which has no subscript
     "₂". Here we register a Unicode TrueType font (Arial) and render CO₂e / m²
     using proper <sub>/<super> markup so they are always correct.

  2. Overlapping columns — the original comparative table's column widths summed
     to ~23 cm on a 17 cm page, so cells collided. Here every cell is a wrapping
     Paragraph and the columns are sized to fit the page width.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── Unicode font registration ─────────────────────────────────────────────────
_FONT = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"
for regular, bold, name in [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf", "Arial"),
    ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf", "SegoeUI"),
]:
    if Path(regular).exists() and Path(bold).exists():
        try:
            pdfmetrics.registerFont(TTFont(name, regular))
            pdfmetrics.registerFont(TTFont(name + "-Bold", bold))
            _FONT, _FONT_BOLD = name, name + "-Bold"
            break
        except Exception:
            continue

# CO₂e and m² rendered via markup so they don't depend on a subscript glyph.
CO2E = "CO<sub>2</sub>e"
M2 = "m<super>2</super>"

# ── Colour palette ────────────────────────────────────────────────────────────
NAVY = colors.HexColor("#1a3a5c")
TEAL = colors.HexColor("#2a7d6f")
LIGHT_BLUE = colors.HexColor("#dce8f5")
GREEN_HIGHLIGHT = colors.HexColor("#d4edda")
AMBER = colors.HexColor("#fff3cd")
RED_LIGHT = colors.HexColor("#f8d7da")
GREY_LIGHT = colors.HexColor("#f5f5f5")
GREY_MID = colors.HexColor("#cccccc")


def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("RTitle", parent=base["Title"], fontName=_FONT_BOLD,
                                fontSize=22, textColor=NAVY, spaceAfter=4),
        "subtitle": ParagraphStyle("RSub", parent=base["Normal"], fontName=_FONT,
                                   fontSize=11, textColor=TEAL, spaceAfter=2),
        "body": ParagraphStyle("RBody", parent=base["Normal"], fontName=_FONT,
                               fontSize=9, leading=13),
        "small": ParagraphStyle("RSmall", parent=base["Normal"], fontName=_FONT,
                                fontSize=8, textColor=colors.grey, leading=11),
        "big_number": ParagraphStyle("RBigNum", parent=base["Normal"], fontName=_FONT_BOLD,
                                     fontSize=26, textColor=NAVY, alignment=1),
        "big_label": ParagraphStyle("RBigLabel", parent=base["Normal"], fontName=_FONT,
                                    fontSize=8, textColor=colors.grey, alignment=1, leading=10),
        "cell": ParagraphStyle("RCell", parent=base["Normal"], fontName=_FONT,
                               fontSize=7.5, leading=9),
        "cell_r": ParagraphStyle("RCellR", parent=base["Normal"], fontName=_FONT,
                                 fontSize=7.5, leading=9, alignment=2),
        "cell_h": ParagraphStyle("RCellH", parent=base["Normal"], fontName=_FONT_BOLD,
                                 fontSize=7.5, leading=9, textColor=colors.white),
    }


def _header_table(text: str, width: float = 17 * cm) -> Table:
    t = Table([[text]], colWidths=[width])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), _FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


def generate_report(
    df: pd.DataFrame,
    stats: dict,
    output_path: str | Path,
    project_name: str = "Surround Carbon Assessment",
    site_location: str = "",
    building_type: str = "",
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path), pagesize=A4,
        rightMargin=2 * cm, leftMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
    )
    s = _styles()
    story = []

    # ── Cover ─────────────────────────────────────────────────────────────────
    cover = Table([["SURROUND\nMaterial Carbon Passport"]], colWidths=[17 * cm])
    cover.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), _FONT_BOLD),
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
    story.append(_header_table("1. Material Carbon Passport – Key Metrics"))
    story.append(Spacer(1, 0.3 * cm))

    intensity = stats.get("intensity_kg_m2", 0)
    benchmark = stats.get("benchmark_kg_m2", 240)
    vs_pct = stats.get("vs_benchmark_pct", 0)
    benchmark_colour = GREEN_HIGHLIGHT if vs_pct <= 0 else (AMBER if vs_pct <= 20 else RED_LIGHT)
    benchmark_label = "below benchmark" if vs_pct <= 0 else "above benchmark"

    kpi_data = [
        [
            Paragraph(f"{stats.get('total_co2e_t', 0):.2f} t", s["big_number"]),
            Paragraph(f"{intensity:.0f} kg/{M2}", s["big_number"]),
            Paragraph(f"{vs_pct:+.1f}%", s["big_number"]),
        ],
        [
            Paragraph(f"Total {CO2E} (tonnes)", s["big_label"]),
            Paragraph("Carbon Intensity", s["big_label"]),
            Paragraph(f"vs {benchmark} kg/{M2} benchmark ({benchmark_label})", s["big_label"]),
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
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 0.4 * cm))

    # ── Section 2 — Carbon Split by Element ───────────────────────────────────
    story.append(_header_table("2. Carbon Split by Building Element"))
    story.append(Spacer(1, 0.3 * cm))

    split = stats.get("carbon_split_by_type", {})
    total_co2e = stats.get("total_co2e_kg", 1)
    split_data = [[
        Paragraph("Element", s["cell_h"]),
        Paragraph(f"{CO2E} (kg)", s["cell_h"]),
        Paragraph(f"{CO2E} (t)", s["cell_h"]),
        Paragraph("% of Total", s["cell_h"]),
    ]]
    for element, co2e in split.items():
        pct = (co2e / total_co2e * 100) if total_co2e else 0
        split_data.append([
            Paragraph(str(element), s["cell"]),
            Paragraph(f"{co2e:,.1f}", s["cell_r"]),
            Paragraph(f"{co2e / 1000:.2f}", s["cell_r"]),
            Paragraph(f"{pct:.1f}%", s["cell_r"]),
        ])
    split_data.append([
        Paragraph("TOTAL", s["cell_h"]),
        Paragraph(f"{total_co2e:,.1f}", s["cell_r"]),
        Paragraph(f"{total_co2e / 1000:.2f}", s["cell_r"]),
        Paragraph("100%", s["cell_r"]),
    ])

    split_table = Table(split_data, colWidths=[5 * cm, 4 * cm, 4 * cm, 4 * cm])
    split_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("BACKGROUND", (0, -1), (-1, -1), LIGHT_BLUE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [GREY_LIGHT, colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, GREY_MID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    # Make the TOTAL row label bold-on-light (override white header style).
    split_data[-1][0] = Paragraph("TOTAL", ParagraphStyle(
        "tot", parent=s["cell"], fontName=_FONT_BOLD))
    story.append(split_table)
    story.append(Spacer(1, 0.5 * cm))

    # ── Section 3 — Material Comparative Table (FIXED widths + wrapping) ───────
    story.append(PageBreak())
    story.append(_header_table("3. Material Comparative Table – Top Choice per Surface"))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        "The table below shows the highest-ranked material option for each building "
        "surface, selected by combined score (70% lowest carbon / 30% nearest supplier).",
        s["body"],
    ))
    story.append(Spacer(1, 0.3 * cm))

    if not df.empty:
        # (header label, source column, width cm, right-align?) — sums to 17 cm.
        spec = [
            ("Surface", "Surface Type", 1.7, False),
            ("Material", "Material Category", 1.8, False),
            ("Product Name", "Product Name", 4.0, False),
            ("Manufacturer", "Manufacturer", 3.3, False),
            ("Country", "Country", 1.4, False),
            (f"{CO2E} (kg)", "Total CO₂e (kg)", 2.5, True),
            (f"{CO2E}/{M2}", "CO₂e per m² (kg/m²)", 2.3, True),
        ]
        spec = [x for x in spec if x[1] in df.columns]
        header = [Paragraph(label, s["cell_h"]) for label, _, _, _ in spec]
        table_data = [header]
        for _, row in df.iterrows():
            table_data.append([
                Paragraph(str(row.get(col, "")), s["cell_r"] if right else s["cell"])
                for _, col, _, right in spec
            ])
        col_widths = [w * cm for _, _, w, _ in spec]

        mat_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        mat_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [GREY_LIGHT, colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.4, GREY_MID),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(mat_table)

    story.append(Spacer(1, 0.5 * cm))

    # ── Section 4 — Baseline vs Altered Scenario ──────────────────────────────
    story.append(_header_table("4. Baseline vs Altered Scenario"))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        "Comparison of the selected EPD-verified material set against the 22@ Poblenou "
        f"district average of 207 kg {CO2E}/{M2} and the industry benchmark of "
        f"{benchmark} kg {CO2E}/{M2}.",
        s["body"],
    ))
    story.append(Spacer(1, 0.3 * cm))

    scenario_rows = [
        ("Scenario", f"Intensity (kg {CO2E}/{M2})", "vs Benchmark", True),
        ("22@ District Average", "207", f"{((207 - benchmark) / benchmark * 100):+.1f}%", False),
        ("Industry Benchmark", str(benchmark), "0.0%", False),
        ("This Design (EPD-verified)", f"{intensity:.1f}", f"{vs_pct:+.1f}%", False),
    ]
    scenario_data = []
    for c0, c1, c2, is_head in scenario_rows:
        style = s["cell_h"] if is_head else s["cell"]
        style_c = s["cell_h"] if is_head else s["cell_r"]
        scenario_data.append([
            Paragraph(c0, style), Paragraph(c1, style_c), Paragraph(c2, style_c)])
    scen_table = Table(scenario_data, colWidths=[7 * cm, 5.5 * cm, 4.5 * cm])
    scen_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("BACKGROUND", (0, 3), (-1, 3), benchmark_colour),
        ("ROWBACKGROUNDS", (0, 1), (-1, 2), [GREY_LIGHT, colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, GREY_MID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
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
        f"Generated by Surround Carbon Pipeline · Stage A1–A3 only · "
        f"Data sourced from EPD database (2050-materials.com) · "
        f"Benchmark: 240 kg {CO2E}/{M2} (industry standard)",
        s["small"],
    ))

    doc.build(story)
    return output_path

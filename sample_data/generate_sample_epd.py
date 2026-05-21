"""
Generates sample EPD (Environmental Product Declaration) PDFs for testing the parsing pipeline.
Each PDF mimics the structure of real EPD datasheets from databases like EPD Australasia or ECO Portal.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT


SAMPLE_EPDS = [
    {
        "product_name": "StructaBoard Timber CLT Panel",
        "company": "AusTimber Innovations Pty Ltd",
        "location": "Melbourne, VIC, Australia",
        "country": "AU",
        "material_category": "Wood",
        "declared_unit": "1 m³ of cross-laminated timber panel",
        "gwp_a1_a3": 58.2,           # kg CO2e per m3 (production stage)
        "gwp_per_kg": 0.0291,         # kg CO2e per kg
        "density_kg_m3": 500,
        "functional_unit": "1 m³",
        "valid_until": "2027-03-15",
        "epd_number": "EPD-AUS-2024-0142",
        "standard": "ISO 14044, EN 15804+A2",
        "notes": "Includes A1–A3 (cradle to gate). Carbon stored in wood not included in GWP.",
    },
    {
        "product_name": "EcoSlab Ready-Mix Concrete 32 MPa",
        "company": "Concrete Solutions Pty Ltd",
        "location": "Sydney, NSW, Australia",
        "country": "AU",
        "material_category": "Concrete",
        "declared_unit": "1 m³ of ready-mix concrete",
        "gwp_a1_a3": 280.5,
        "gwp_per_kg": 0.1122,
        "density_kg_m3": 2500,
        "functional_unit": "1 m³",
        "valid_until": "2026-11-30",
        "epd_number": "EPD-AUS-2023-0089",
        "standard": "ISO 14044, EN 15804+A2",
        "notes": "32 MPa compressive strength. SCM content 30% fly ash replacement.",
    },
    {
        "product_name": "GreenSteel Structural Section (RHS 150x100)",
        "company": "Pacific Steel Manufacturing",
        "location": "Brisbane, QLD, Australia",
        "country": "AU",
        "material_category": "Steel",
        "declared_unit": "1 tonne of hot-rolled structural steel section",
        "gwp_a1_a3": 1820.0,
        "gwp_per_kg": 1.820,
        "density_kg_m3": 7850,
        "functional_unit": "1 tonne",
        "valid_until": "2027-06-01",
        "epd_number": "EPD-AUS-2024-0201",
        "standard": "ISO 14044, EN 15804+A2",
        "notes": "Electric arc furnace production. 93% recycled content.",
    },
]


def build_epd_pdf(epd: dict, output_path: str):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "EPDTitle",
        parent=styles["Title"],
        fontSize=16,
        textColor=colors.HexColor("#1a3a5c"),
        spaceAfter=6,
    )
    heading_style = ParagraphStyle(
        "EPDHeading",
        parent=styles["Heading2"],
        fontSize=11,
        textColor=colors.HexColor("#1a3a5c"),
        spaceBefore=12,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "EPDBody",
        parent=styles["Normal"],
        fontSize=9,
        leading=14,
    )
    small_style = ParagraphStyle(
        "EPDSmall",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.grey,
    )

    story = []

    # Header banner
    header_data = [["ENVIRONMENTAL PRODUCT DECLARATION"]]
    header_table = Table(header_data, colWidths=[17 * cm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1a3a5c")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 13),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.4 * cm))

    # Product title
    story.append(Paragraph(epd["product_name"], title_style))
    story.append(Paragraph(f"{epd['company']} | {epd['location']}", body_style))
    story.append(Spacer(1, 0.3 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a3a5c")))
    story.append(Spacer(1, 0.3 * cm))

    # Product information table
    story.append(Paragraph("1. Product Information", heading_style))
    info_data = [
        ["EPD Number", epd["epd_number"]],
        ["Material Category", epd["material_category"]],
        ["Manufacturer", epd["company"]],
        ["Location of Production", epd["location"]],
        ["Country", epd["country"]],
        ["Declared Unit", epd["declared_unit"]],
        ["Functional Unit", epd["functional_unit"]],
        ["Standard", epd["standard"]],
        ["Valid Until", epd["valid_until"]],
    ]
    info_table = Table(info_data, colWidths=[6 * cm, 11 * cm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dce8f5")),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f5f9ff"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.3 * cm))

    # Physical properties
    story.append(Paragraph("2. Physical Properties", heading_style))
    phys_data = [
        ["Property", "Value", "Unit"],
        ["Density", str(epd["density_kg_m3"]), "kg/m³"],
        ["Compressive Strength", "N/A" if epd["material_category"] != "Concrete" else "32", "MPa"],
    ]
    phys_table = Table(phys_data, colWidths=[7 * cm, 5 * cm, 5 * cm])
    phys_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f5f9ff"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(phys_table)
    story.append(Spacer(1, 0.3 * cm))

    # LCA results — the key section for parsing
    story.append(Paragraph("3. Life Cycle Assessment Results — Global Warming Potential (GWP)", heading_style))
    story.append(Paragraph(
        "Results are expressed per declared unit. A1–A3 represents the cradle-to-gate production stage.",
        body_style,
    ))
    story.append(Spacer(1, 0.2 * cm))

    lca_data = [
        ["Indicator", "A1–A3\n(Production)", "Unit"],
        ["Global Warming Potential (GWP)", f"{epd['gwp_a1_a3']:.1f}", f"kg CO₂e / {epd['functional_unit']}"],
        ["GWP per kg", f"{epd['gwp_per_kg']:.4f}", "kg CO₂e / kg"],
        ["Ozone Depletion Potential (ODP)", "< 1.0e-6", "kg CFC-11e"],
        ["Acidification Potential (AP)", "N/A", "mol H+ eq"],
        ["Eutrophication Potential (EP)", "N/A", "kg PO₄³⁻ eq"],
    ]
    lca_table = Table(lca_data, colWidths=[8 * cm, 4 * cm, 5 * cm])
    lca_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 1), (0, 2), "Helvetica-Bold"),
        ("BACKGROUND", (0, 1), (-1, 2), colors.HexColor("#d4edda")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 3), (-1, -1), [colors.HexColor("#f5f9ff"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
    ]))
    story.append(lca_table)
    story.append(Spacer(1, 0.3 * cm))

    # Notes
    story.append(Paragraph("4. Additional Notes", heading_style))
    story.append(Paragraph(epd["notes"], body_style))
    story.append(Spacer(1, 0.5 * cm))

    # Footer
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        f"This EPD has been prepared in accordance with {epd['standard']}. "
        f"EPD Number: {epd['epd_number']}. Valid until: {epd['valid_until']}.",
        small_style,
    ))

    doc.build(story)
    print(f"Generated: {output_path}")


if __name__ == "__main__":
    import os

    output_dir = os.path.join(os.path.dirname(__file__), "epd_pdfs")
    os.makedirs(output_dir, exist_ok=True)

    for epd in SAMPLE_EPDS:
        filename = epd["product_name"].replace(" ", "_").replace("/", "-") + ".pdf"
        output_path = os.path.join(output_dir, filename)
        build_epd_pdf(epd, output_path)

    print(f"\nAll sample EPDs saved to: {output_dir}")

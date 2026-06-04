"""
Step 4 — Embodied Carbon Calculation Engine
Combines EPD carbon factors with surface geometry to produce total CO₂e
for each candidate material on a given surface.
"""

from dataclasses import dataclass

from pipeline.pdf_parser import EPDRecord
from pipeline.unit_parser import MeasurementBasis, UnitRule, get_unit_rule


@dataclass
class SurfaceInput:
    """Geometry of a single building surface from Stage 2."""
    surface_id: str           # e.g. "roof_01", "wall_north"
    surface_type: str         # e.g. "roof", "wall", "floor"
    area_m2: float
    volume_m3: float | None = None   # relevant for thick elements like walls/slabs
    material_category: str = ""      # user-specified search term, e.g. "timber"


@dataclass
class CarbonResult:
    """Carbon calculation result for one EPD record applied to one surface."""
    surface_id: str
    product_name: str
    company: str
    location: str
    country: str
    epd_number: str
    material_category: str
    declared_unit: str
    gwp_per_declared_unit: float | None
    gwp_per_kg: float | None
    area_m2: float
    volume_m3: float | None
    total_co2e_kg: float            # the key output: kg CO₂e for this surface
    unit_basis: str                 # which measurement basis was used
    notes: str = ""


def calculate_carbon(record: EPDRecord, surface: SurfaceInput) -> CarbonResult | None:
    """
    Calculate total embodied carbon (kg CO₂e) for one EPD material on one surface.

    Returns None if insufficient data is available to make a calculation.
    """
    category = record.material_category or surface.material_category
    rule: UnitRule = get_unit_rule(category)

    gwp_unit = record.gwp_per_declared_unit
    gwp_kg = record.gwp_per_kg
    area = surface.area_m2
    volume = surface.volume_m3

    total_co2e: float | None = None
    notes = ""

    if rule.basis == MeasurementBasis.PER_M2:
        if gwp_unit is not None:
            total_co2e = gwp_unit * area
            notes = f"{gwp_unit} kg CO₂e/m² × {area} m²"

    elif rule.basis == MeasurementBasis.PER_M3:
        if volume is not None and gwp_unit is not None:
            total_co2e = gwp_unit * volume
            notes = f"{gwp_unit} kg CO₂e/m³ × {volume} m³"
        elif area is not None and gwp_unit is not None and record.density_kg_m3:
            # Estimate volume from area assuming a standard thickness for this category
            # Only use this as a fallback — volume from Stage 2 is preferred
            typical_thickness = _typical_thickness_m(surface.surface_type)
            est_volume = area * typical_thickness
            total_co2e = gwp_unit * est_volume
            notes = f"{gwp_unit} kg CO₂e/m³ × {est_volume:.2f} m³ (estimated at {typical_thickness}m thick)"

    elif rule.basis == MeasurementBasis.PER_KG:
        factor = gwp_kg if gwp_kg is not None else gwp_unit
        if factor is not None and rule.typical_density_kg_m3:
            typical_thickness = _typical_thickness_m(surface.surface_type)
            mass_kg = area * typical_thickness * rule.typical_density_kg_m3
            total_co2e = factor * mass_kg
            notes = (
                f"{factor} kg CO₂e/kg × {mass_kg:.1f} kg "
                f"(area {area} m² × {typical_thickness}m × {rule.typical_density_kg_m3} kg/m³)"
            )
        elif factor is not None and volume is not None and rule.typical_density_kg_m3:
            mass_kg = volume * rule.typical_density_kg_m3
            total_co2e = factor * mass_kg
            notes = f"{factor} kg CO₂e/kg × {mass_kg:.1f} kg (from volume)"

    elif rule.basis == MeasurementBasis.PER_PIECE:
        # Can't calculate without piece count — flag for manual input
        notes = "Per-piece material: piece count required for carbon calculation"

    if total_co2e is None:
        return None

    return CarbonResult(
        surface_id=surface.surface_id,
        product_name=record.product_name,
        company=record.company,
        location=record.location,
        country=record.country,
        epd_number=record.epd_number,
        material_category=category,
        declared_unit=record.declared_unit,
        gwp_per_declared_unit=gwp_unit,
        gwp_per_kg=gwp_kg,
        area_m2=area,
        volume_m3=volume,
        total_co2e_kg=round(total_co2e, 2),
        unit_basis=rule.basis.value,
        notes=notes,
    )


def calculate_all(
    records: list[EPDRecord],
    surface: SurfaceInput,
) -> list[CarbonResult]:
    """Run calculate_carbon for every EPD record against a surface, skipping None results."""
    results = []
    for record in records:
        result = calculate_carbon(record, surface)
        if result is not None:
            results.append(result)
    return results


def _typical_thickness_m(surface_type: str) -> float:
    """
    Fallback thickness assumptions used only when Stage 2 doesn't supply volume.
    These are indicative values — real volume from Stage 2 always takes priority.
    """
    defaults = {
        "wall":       0.20,
        "roof":       0.15,
        "floor":      0.25,
        "slab":       0.25,
        "foundation": 0.40,
        "ceiling":    0.10,
    }
    return defaults.get(surface_type.lower(), 0.20)

"""
Step 3 — Rule-Based Material Unit Parser
Maps a material category to its standard measurement convention so the
carbon calculation engine knows how to convert between area/volume and mass.
Rules are based on common EPD declared units and industry convention.
"""

from dataclasses import dataclass
from enum import Enum


class MeasurementBasis(Enum):
    PER_KG = "per_kg"           # carbon factor is kg CO2e / kg
    PER_M2 = "per_m2"           # carbon factor is kg CO2e / m²
    PER_M3 = "per_m3"           # carbon factor is kg CO2e / m³
    PER_PIECE = "per_piece"     # carbon factor is kg CO2e / unit/piece


@dataclass
class UnitRule:
    basis: MeasurementBasis
    # Typical density in kg/m³ — used to convert m³ → kg when basis is PER_KG
    # None means no conversion needed (area/volume is the primary quantity)
    typical_density_kg_m3: float | None = None
    notes: str = ""


# ── Rule table ────────────────────────────────────────────────────────────────
# Keys are lowercase material category names (partial match allowed)

UNIT_RULES: dict[str, UnitRule] = {
    # Structural / bulk materials — sold and EPD'd by weight
    "concrete":     UnitRule(PER_M3 := MeasurementBasis.PER_M3, 2400, "ready-mix, precast"),
    "cement":       UnitRule(MeasurementBasis.PER_KG, 1500),
    "steel":        UnitRule(MeasurementBasis.PER_KG, 7850, "structural sections, rebar"),
    "aluminium":    UnitRule(MeasurementBasis.PER_KG, 2700),
    "aluminum":     UnitRule(MeasurementBasis.PER_KG, 2700),
    "copper":       UnitRule(MeasurementBasis.PER_KG, 8960),
    "iron":         UnitRule(MeasurementBasis.PER_KG, 7870),

    # Timber / wood — EPD'd per m³
    "wood":         UnitRule(MeasurementBasis.PER_M3, 500, "CLT, glulam, solid timber"),
    "timber":       UnitRule(MeasurementBasis.PER_M3, 500),
    "clt":          UnitRule(MeasurementBasis.PER_M3, 500, "cross-laminated timber"),
    "glulam":       UnitRule(MeasurementBasis.PER_M3, 480),
    "plywood":      UnitRule(MeasurementBasis.PER_M3, 550),
    "mdf":          UnitRule(MeasurementBasis.PER_M3, 700),
    "osb":          UnitRule(MeasurementBasis.PER_M3, 620),

    # Masonry — EPD'd per piece or per m²
    "brick":        UnitRule(MeasurementBasis.PER_PIECE, None, "standard clay brick"),
    "blocks":       UnitRule(MeasurementBasis.PER_PIECE, None, "AAC, concrete blocks"),
    "aac":          UnitRule(MeasurementBasis.PER_M3, 550, "autoclaved aerated concrete"),

    # Cladding / finishes — typically per m²
    "tile":         UnitRule(MeasurementBasis.PER_M2, None, "ceramic, porcelain"),
    "tiles":        UnitRule(MeasurementBasis.PER_M2, None),
    "glass":        UnitRule(MeasurementBasis.PER_M2, None, "glazing, curtain wall"),
    "glazing":      UnitRule(MeasurementBasis.PER_M2, None),
    "cladding":     UnitRule(MeasurementBasis.PER_M2, None),
    "render":       UnitRule(MeasurementBasis.PER_M2, None),
    "plaster":      UnitRule(MeasurementBasis.PER_M2, None),
    "carpet":       UnitRule(MeasurementBasis.PER_M2, None),
    "flooring":     UnitRule(MeasurementBasis.PER_M2, None),
    "insulation":   UnitRule(MeasurementBasis.PER_M2, None, "batts, boards"),

    # Roofing
    "roofing":      UnitRule(MeasurementBasis.PER_M2, None),
    "membrane":     UnitRule(MeasurementBasis.PER_M2, None),

    # Windows / doors — per piece
    "window":       UnitRule(MeasurementBasis.PER_PIECE, None),
    "windows":      UnitRule(MeasurementBasis.PER_PIECE, None),
    "door":         UnitRule(MeasurementBasis.PER_PIECE, None),
    "doors":        UnitRule(MeasurementBasis.PER_PIECE, None),
}

_DEFAULT_RULE = UnitRule(MeasurementBasis.PER_KG, None, "fallback — no specific rule matched")


def get_unit_rule(material_category: str) -> UnitRule:
    """
    Return the UnitRule for a given material category string.
    Matches by checking if any rule key appears in the lowercased category.
    Falls back to PER_KG if no rule matches.
    """
    normalised = material_category.lower().strip()

    # Exact match first
    if normalised in UNIT_RULES:
        return UNIT_RULES[normalised]

    # Partial match — find any rule key that is a substring of the category
    for key, rule in UNIT_RULES.items():
        if key in normalised:
            return rule

    return _DEFAULT_RULE


def resolve_gwp_per_m2(
    gwp_per_declared_unit: float,
    gwp_per_kg: float | None,
    rule: UnitRule,
    declared_unit_volume_m3: float = 1.0,
) -> float:
    """
    Convert the EPD's GWP value to kg CO₂e per m² of surface area.
    This is the normalised form used by the carbon calculation engine.

    Args:
        gwp_per_declared_unit: Raw GWP from EPD (per declared unit)
        gwp_per_kg:            GWP per kg if available
        rule:                  UnitRule for this material
        declared_unit_volume_m3: Volume of the declared unit in m³ (default 1 m³)

    Returns:
        gwp in kg CO₂e / m²
    """
    basis = rule.basis

    if basis == MeasurementBasis.PER_KG and gwp_per_kg is not None:
        # Already per kg — need density to get per m²
        # Caller must handle thickness separately; return per-kg as-is
        return gwp_per_kg

    if basis == MeasurementBasis.PER_M2:
        return gwp_per_declared_unit

    if basis == MeasurementBasis.PER_M3:
        # Divide by m³ to get per m³, then caller multiplies by volume
        return gwp_per_declared_unit / declared_unit_volume_m3

    # PER_PIECE or fallback — return raw value; caller counts pieces
    return gwp_per_declared_unit

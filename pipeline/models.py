"""Data structures shared across the Stage 4 visualisation pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SelectedMaterial:
    """One winning material for one surface, read from the comparative table."""

    surface_id: str
    surface_type: str            # Roof, Wall, Floor, ...
    material_category: str       # wood, concrete, steel, ...
    product_name: str
    manufacturer: str
    location: str
    country: str
    area_m2: float
    total_co2e_kg: float
    co2e_per_m2: float
    epd_number: str = ""

    @property
    def label(self) -> str:
        return f"{self.surface_type}: {self.product_name}"


@dataclass
class TextureAsset:
    """A texture image resolved for a selected material."""

    surface_id: str
    material_category: str
    image_path: str
    source: str                  # "scraped" | "fallback" | "procedural"
    source_url: Optional[str] = None


@dataclass
class TexturedSurface:
    """A selected material paired with its resolved texture (loop output)."""

    material: SelectedMaterial
    texture: TextureAsset


@dataclass
class RenderResult:
    """Final visualisation output."""

    image_path: str
    mode: str                    # "gemini" | "mock"
    prompt: str
    surfaces: list = field(default_factory=list)

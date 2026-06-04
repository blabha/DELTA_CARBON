"""
Step 5 — Ranking Algorithm
Ranks candidate materials by two criteria:
  1. Geographic proximity to the project site (to minimise transport emissions)
  2. Lowest total embodied carbon (kg CO₂e)
Returns the top N options as a combined ranked list.
"""

from dataclasses import dataclass

from geopy.distance import geodesic
from geopy.geocoders import Nominatim

from pipeline.carbon_calc import CarbonResult

# Geocoder instance — shared, rate-limited by geopy
_geocoder = Nominatim(user_agent="surround_carbon_pipeline")

# Cache so we don't re-geocode the same location string twice per run
_geo_cache: dict[str, tuple[float, float] | None] = {}


@dataclass
class RankedResult:
    rank: int
    carbon_result: CarbonResult
    distance_km: float | None       # distance from project site to manufacturer
    geo_score: float                # 0.0 (far) – 1.0 (same location)
    carbon_score: float             # 0.0 (highest carbon) – 1.0 (lowest carbon)
    combined_score: float           # weighted combination used for final rank


def _geocode(location_str: str) -> tuple[float, float] | None:
    """Return (lat, lon) for a location string, or None if geocoding fails."""
    if location_str in _geo_cache:
        return _geo_cache[location_str]
    try:
        result = _geocoder.geocode(location_str, timeout=5)
        coords = (result.latitude, result.longitude) if result else None
    except Exception:
        coords = None
    _geo_cache[location_str] = coords
    return coords


def _normalise(values: list[float]) -> list[float]:
    """Min-max normalise a list of floats to [0, 1]."""
    mn, mx = min(values), max(values)
    if mx == mn:
        return [1.0] * len(values)
    return [(v - mn) / (mx - mn) for v in values]


def rank_materials(
    results: list[CarbonResult],
    site_location: str,
    top_n: int = 5,
    geo_weight: float = 0.3,
    carbon_weight: float = 0.7,
) -> list[RankedResult]:
    """
    Rank a list of CarbonResults for a single surface.

    Args:
        results:        Output of calculate_all() for one surface.
        site_location:  Human-readable project address/city for geocoding,
                        e.g. "22@ Poblenou, Barcelona, Spain"
        top_n:          How many results to return (default 5).
        geo_weight:     Weight given to proximity (default 0.3).
        carbon_weight:  Weight given to low carbon (default 0.7).

    Returns:
        Sorted list of RankedResult, best first.
    """
    if not results:
        return []

    site_coords = _geocode(site_location)

    # Compute distances
    distances: list[float | None] = []
    for r in results:
        if site_coords and r.location:
            mfr_coords = _geocode(r.location)
            if mfr_coords:
                distances.append(geodesic(site_coords, mfr_coords).km)
            else:
                distances.append(None)
        else:
            distances.append(None)

    # Replace None distances with the maximum known distance (worst case)
    known = [d for d in distances if d is not None]
    fallback_dist = max(known) * 1.5 if known else 10_000.0
    filled_distances = [d if d is not None else fallback_dist for d in distances]

    carbon_values = [r.total_co2e_kg for r in results]

    # Normalise: for distance, lower = better → invert after normalising
    norm_dist = _normalise(filled_distances)
    geo_scores = [1.0 - nd for nd in norm_dist]   # high score = close

    # For carbon, lower = better → invert after normalising
    norm_carbon = _normalise(carbon_values)
    carbon_scores = [1.0 - nc for nc in norm_carbon]

    ranked = []
    for i, (r, dist, gs, cs) in enumerate(zip(results, filled_distances, geo_scores, carbon_scores)):
        combined = geo_weight * gs + carbon_weight * cs
        ranked.append(RankedResult(
            rank=0,
            carbon_result=r,
            distance_km=distances[i],
            geo_score=round(gs, 4),
            carbon_score=round(cs, 4),
            combined_score=round(combined, 4),
        ))

    ranked.sort(key=lambda x: x.combined_score, reverse=True)

    top = ranked[:top_n]
    for i, item in enumerate(top, start=1):
        item.rank = i

    return top

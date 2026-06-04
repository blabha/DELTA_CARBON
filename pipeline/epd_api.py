"""
Step 1 — EPD API Integration
Searches the 2050-materials EPD database by material keyword and country,
returns a list of product records including their PDF datasheet URLs.
Requires EPD_API_TOKEN in .env (get one at https://app.2050-materials.com/).
"""

import os
import requests
from pathlib import Path
from dotenv import load_dotenv
from aecdata.client import User

load_dotenv()

# GWP field name used across the pipeline
GWP_FIELD = "global_warming_potential_total"


def _get_client() -> User:
    token = os.getenv("EPD_API_TOKEN")
    if not token:
        raise EnvironmentError(
            "EPD_API_TOKEN not set. Copy .env.example to .env and add your token "
            "from https://app.2050-materials.com/"
        )
    return User(developer_token=token)


def search_epds(keyword: str, country: str = "AU", max_results: int = 20) -> list[dict]:
    """
    Search the EPD database for products matching a keyword and country.

    Args:
        keyword:     Material search term, e.g. "timber", "concrete", "steel"
        country:     ISO 3166-1 alpha-2 country code, e.g. "AU", "ES", "GB"
        max_results: Cap on how many records to return (API pages at 200 per call)

    Returns:
        List of raw product dicts from the API. Each dict contains product
        metadata and LCA impact values including GWP.
    """
    client = _get_client()
    products = client.get_products(
        search=keyword,
        country=country,
    )
    return products[:max_results]


def download_pdf(product: dict, output_dir: str | Path) -> Path | None:
    """
    Download the EPD PDF datasheet for a single product record.

    Args:
        product:    Product dict returned by search_epds()
        output_dir: Directory to save the downloaded PDF

    Returns:
        Path to saved PDF, or None if no PDF URL was found.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_url = product.get("epd_url") or product.get("pdf_url") or product.get("document_url")
    if not pdf_url:
        return None

    product_name = product.get("name", "unknown").replace("/", "-").replace(" ", "_")
    pdf_path = output_dir / f"{product_name}.pdf"

    response = requests.get(pdf_url, timeout=30)
    response.raise_for_status()
    pdf_path.write_bytes(response.content)
    return pdf_path


def fetch_and_download(
    keyword: str,
    country: str = "AU",
    output_dir: str | Path = "downloads/epd_pdfs",
    max_results: int = 20,
) -> list[dict]:
    """
    Full Step 1 entry point: search EPDs and download all available PDFs.

    Returns a list of dicts, each with:
        - 'product': raw API product record
        - 'pdf_path': local Path to downloaded PDF (or None if unavailable)
    """
    products = search_epds(keyword, country, max_results)
    results = []
    for product in products:
        pdf_path = download_pdf(product, output_dir)
        results.append({"product": product, "pdf_path": pdf_path})
    return results


def extract_gwp_from_api_record(product: dict) -> float | None:
    """
    Pull the A1–A3 GWP value directly from the API record (kg CO₂e per declared unit).
    Use this when a PDF is unavailable but the API already returned impact data.
    """
    impacts = product.get("impacts", {})
    # Try A1A2A3 combined first, fall back to summing A1+A2+A3
    gwp = (
        impacts.get("A1A2A3", {}).get(GWP_FIELD)
        or impacts.get("A1-A3", {}).get(GWP_FIELD)
    )
    if gwp is not None:
        return float(gwp)

    a1 = impacts.get("A1", {}).get(GWP_FIELD) or 0
    a2 = impacts.get("A2", {}).get(GWP_FIELD) or 0
    a3 = impacts.get("A3", {}).get(GWP_FIELD) or 0
    total = a1 + a2 + a3
    return float(total) if total else None

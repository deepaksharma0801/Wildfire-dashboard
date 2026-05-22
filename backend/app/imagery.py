from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.responses import FileResponse

from app.data import PROJECT_ROOT

IMAGERY_ROOT = PROJECT_ROOT / "data" / "sample" / "imagery"
PRODUCTS_PATH = IMAGERY_ROOT / "imagery_products.json"


class ImageryUnavailable(RuntimeError):
    """Raised when sample imagery metadata or assets are missing."""


def load_products() -> list[dict[str, Any]]:
    if not PRODUCTS_PATH.exists():
        raise ImageryUnavailable("sample imagery product manifest is missing")
    return json.loads(PRODUCTS_PATH.read_text(encoding="utf-8"))


def product_summary(product: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": product["id"],
        "incident_id": product["incident_id"],
        "title": product["title"],
        "source": product["source"],
        "sensor": product["sensor"],
        "before_date": product["before_date"],
        "after_date": product["after_date"],
        "cloud_cover_percent": product["cloud_cover_percent"],
        "burn_area_hectares": product["burn_area_hectares"],
        "dnbr_mean": product["dnbr_mean"],
        "severity_class": product["severity_class"],
        "bounds": product["bounds"],
    }


def search_imagery_products(query: str | None = None) -> dict[str, Any]:
    products = load_products()
    if query:
        normalized = query.lower()
        products = [
            product
            for product in products
            if normalized in product["title"].lower()
            or normalized in product["incident_id"].lower()
            or normalized in product["id"].lower()
        ]

    return {
        "products": [product_summary(product) for product in products],
        "metadata": {
            "count": len(products),
            "source": "sample_sentinel2_burn_scar_demo",
        },
    }


def before_after_product(incident_id: str) -> dict[str, Any]:
    products = load_products()
    product = next(
        (
            candidate
            for candidate in products
            if candidate["incident_id"] == incident_id or candidate["id"] == incident_id
        ),
        products[0] if products else None,
    )
    if product is None:
        raise ImageryUnavailable("no sample imagery products are available")

    response = dict(product)
    response["before_image_url"] = f"/api/imagery/assets/{product['before_asset']}"
    response["after_image_url"] = f"/api/imagery/assets/{product['after_asset']}"
    response["metadata"] = {
        "source": "sample_sentinel2_burn_scar_demo",
        "method": "sample_NBR_dNBR_threshold_overlay",
        "limitations": [
            "Current imagery is a local sample asset for the Phase 8 demo.",
            "Burn scar polygons are sample masks until Sentinel-2 and MTBS ingestion are wired.",
            "dNBR values are representative demo metrics, not validated incident measurements.",
        ],
    }
    return response


def imagery_asset_response(file_name: str) -> FileResponse:
    safe_name = Path(file_name).name
    path = IMAGERY_ROOT / safe_name
    if not path.exists() or path.suffix.lower() not in {".svg", ".png", ".jpg", ".jpeg"}:
        raise ImageryUnavailable("imagery asset not found")
    return FileResponse(path)

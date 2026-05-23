from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.regions import get_region

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "arizona_counties.geojson"
TIGERWEB_COUNTIES_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1/query"
)


def build_tigerweb_url(state_fips: tuple[str, ...]) -> str:
    state_filter = ",".join(f"'{fips}'" for fips in state_fips)
    params = {
        "where": f"STATE IN ({state_filter})",
        "outFields": "STATE,COUNTY,GEOID,NAME,BASENAME,AREALAND,AREAWATER",
        "returnGeometry": "true",
        "f": "geojson",
        "outSR": "4326",
        "resultRecordCount": "2000",
    }
    return f"{TIGERWEB_COUNTIES_URL}?{urlencode(params)}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download county boundaries from Census TIGERweb.")
    parser.add_argument("--region", default="AZ", help="Region/state code: AZ, CA, NV, NM, TX, CO, or southwest.")
    parser.add_argument("--state", default=None, help="Optional state code alias for --region.")
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_PATH,
        type=Path,
        help="GeoJSON output path for county boundaries.",
    )
    parser.add_argument("--timeout", default=30, type=int, help="Download timeout in seconds.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        region = get_region(args.state or args.region)
    except ValueError as error:
        parser.error(str(error))
    url = build_tigerweb_url(region.fips)
    request = Request(url, headers={"User-Agent": "wildfire-geoai/0.1"})

    with urlopen(request, timeout=args.timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))

    features = payload.get("features", [])
    if not features:
        raise RuntimeError(f"Census TIGERweb returned no county features for {region.code}")

    payload["metadata"] = {
        "source": "census_tigerweb_state_county",
        "download_url": url,
        "count": len(features),
        "region": region.code,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Wrote {region.label} county boundaries: {args.output}")
    print(f"County count: {len(features)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

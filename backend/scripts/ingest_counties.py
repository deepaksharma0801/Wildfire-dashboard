from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "arizona_counties.geojson"
TIGERWEB_COUNTIES_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1/query"
)


def build_tigerweb_url() -> str:
    params = {
        "where": "STATE='04'",
        "outFields": "STATE,COUNTY,GEOID,NAME,BASENAME,AREALAND,AREAWATER",
        "returnGeometry": "true",
        "f": "geojson",
        "outSR": "4326",
        "resultRecordCount": "2000",
    }
    return f"{TIGERWEB_COUNTIES_URL}?{urlencode(params)}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download Arizona county boundaries from Census TIGERweb.")
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_PATH,
        type=Path,
        help="GeoJSON output path for Arizona county boundaries.",
    )
    parser.add_argument("--timeout", default=30, type=int, help="Download timeout in seconds.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    url = build_tigerweb_url()
    request = Request(url, headers={"User-Agent": "wildfire-geoai/0.1"})

    with urlopen(request, timeout=args.timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))

    features = payload.get("features", [])
    if not features:
        raise RuntimeError("Census TIGERweb returned no Arizona county features")

    payload["metadata"] = {
        "source": "census_tigerweb_state_county",
        "download_url": url,
        "count": len(features),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Wrote Arizona county boundaries: {args.output}")
    print(f"County count: {len(features)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

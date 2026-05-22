from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "arizona_county_exposure_acs2024.json"
ACS_YEAR = 2024
ACS_URL = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"

VARIABLES = {
    "B01003_001E": "population",
    "B11001_001E": "households",
    "B19013_001E": "median_household_income",
}


def build_acs_url() -> str:
    params = {
        "get": ",".join(["NAME", *VARIABLES.keys()]),
        "for": "county:*",
        "in": "state:04",
    }
    api_key = os.getenv("CENSUS_API_KEY")
    if api_key:
        params["key"] = api_key
    return f"{ACS_URL}?{urlencode(params)}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download Arizona county exposure metrics from ACS 5-year.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_PATH, type=Path, help="JSON output path.")
    parser.add_argument("--timeout", default=30, type=int, help="Download timeout in seconds.")
    return parser


def parse_int(value: str | None) -> int | None:
    if value in (None, "", "-666666666", "-999999999"):
        return None
    return int(float(value))


def main() -> int:
    args = build_parser().parse_args()
    url = build_acs_url()
    request = Request(url, headers={"User-Agent": "wildfire-geoai/0.1"})

    with urlopen(request, timeout=args.timeout) as response:
        body = response.read().decode("utf-8")

    if "missing_key" in body or not body.strip().startswith("["):
        raise RuntimeError(
            "Census API did not return JSON. Set CENSUS_API_KEY and rerun this script."
        )

    payload = json.loads(body)

    header = payload[0]
    rows = []
    for values in payload[1:]:
        row = dict(zip(header, values, strict=True))
        geoid = f"{row['state']}{row['county']}"
        parsed = {
            "geoid": geoid,
            "name": row["NAME"],
            "statefp": row["state"],
            "countyfp": row["county"],
            "source": f"ACS {ACS_YEAR} 5-year",
        }
        for census_variable, field_name in VARIABLES.items():
            parsed[field_name] = parse_int(row.get(census_variable))
        rows.append(parsed)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    print(f"Wrote ACS county exposure data: {args.output}")
    print(f"County count: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

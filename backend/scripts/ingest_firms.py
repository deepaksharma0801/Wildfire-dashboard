from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.firms import (
    ARIZONA_BBOX,
    DEFAULT_FIRMS_SOURCE,
    FIRMS_SOURCE_OPTIONS,
    bbox_to_api_value,
    download_firms_csv,
    normalize_firms_csv,
    parse_bbox_value,
    write_json,
)
from app.regions import get_region

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw" / "firms"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "firms_arizona_latest.geojson"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download and normalize NASA FIRMS fire detections.")
    parser.add_argument(
        "--map-key",
        default=os.getenv("FIRMS_MAP_KEY"),
        help="NASA FIRMS MAP_KEY. Defaults to FIRMS_MAP_KEY env var.",
    )
    parser.add_argument(
        "--source",
        default=DEFAULT_FIRMS_SOURCE,
        choices=FIRMS_SOURCE_OPTIONS,
        help="FIRMS satellite product source.",
    )
    parser.add_argument(
        "--region",
        default="AZ",
        help="Region code used when --bbox is omitted. One of AZ, CA, NV, NM, TX, CO, southwest.",
    )
    parser.add_argument(
        "--bbox",
        default=None,
        help="west,south,east,north bounding box. Defaults to the selected region.",
    )
    parser.add_argument(
        "--day-range",
        default=3,
        type=int,
        help="Number of days to request. FIRMS Area API supports 1 through 5.",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Optional YYYY-MM-DD start date. Omit for the most recent detections.",
    )
    parser.add_argument(
        "--raw-dir",
        default=DEFAULT_RAW_DIR,
        type=Path,
        help="Directory for raw FIRMS CSV downloads.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_PATH,
        type=Path,
        help="Normalized GeoJSON output path served by the API.",
    )
    parser.add_argument(
        "--timeout",
        default=30,
        type=int,
        help="Download timeout in seconds.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.map_key:
        parser.error("missing FIRMS MAP_KEY; pass --map-key or set FIRMS_MAP_KEY")

    try:
        region = get_region(args.region)
    except ValueError as error:
        parser.error(str(error))

    bbox = parse_bbox_value(args.bbox) if args.bbox else region.bbox
    csv_text, url = download_firms_csv(
        map_key=args.map_key,
        source=args.source,
        bbox=bbox,
        day_range=args.day_range,
        date=args.date,
        timeout_seconds=args.timeout,
    )

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    raw_path = args.raw_dir / f"{args.source.lower()}_{timestamp}.csv"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(csv_text, encoding="utf-8")

    state = region.code if region.code != "southwest" else "SW"
    collection = normalize_firms_csv(csv_text, source=args.source, state=state)
    collection["metadata"]["download_url"] = url.replace(args.map_key, "[MAP_KEY]")
    collection["metadata"]["raw_csv_path"] = str(raw_path)
    collection["metadata"]["bbox"] = bbox_to_api_value(bbox)
    collection["metadata"]["region"] = region.code
    collection["metadata"]["day_range"] = args.day_range
    collection["metadata"]["date"] = args.date

    write_json(args.output, collection)

    print(f"Downloaded FIRMS CSV: {raw_path}")
    print(f"Wrote normalized GeoJSON: {args.output}")
    print(f"Normalized detections: {collection['metadata']['count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

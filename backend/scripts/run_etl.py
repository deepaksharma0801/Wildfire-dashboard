from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.data import load_county_collection, load_fire_collection
from app.regions import get_region
from app.risk_evaluation import EVALUATION_PATH, write_risk_evaluation

DEFAULT_LOG_DIR = PROJECT_ROOT / "data" / "processed" / "etl_runs"
PROCESSED_COUNTIES_PATH = PROJECT_ROOT / "data" / "processed" / "arizona_counties.geojson"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_step(command: list[str], *, env: dict[str, str] | None = None) -> dict[str, Any]:
    started_at = utc_now()
    result = subprocess.run(
        command,
        cwd=BACKEND_ROOT,
        env={**os.environ, **(env or {})},
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "command": command,
        "started_at": started_at,
        "finished_at": utc_now(),
        "status": "completed" if result.returncode == 0 else "failed",
        "returncode": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }


def skipped_step(name: str, reason: str) -> dict[str, Any]:
    return {
        "name": name,
        "started_at": utc_now(),
        "finished_at": utc_now(),
        "status": "skipped",
        "reason": reason,
    }


def verify_sample_data(region_code: str) -> dict[str, Any]:
    fires, fire_source = load_fire_collection("sample")
    counties, county_source = load_county_collection()
    return {
        "name": "verify_sample_data",
        "status": "completed",
        "region": region_code,
        "fire_source": fire_source,
        "fire_count": len(fires.get("features", [])),
        "county_source": county_source,
        "county_count": len(counties.get("features", [])),
    }


def refresh_evaluation(output_path: Path) -> dict[str, Any]:
    evaluation = write_risk_evaluation(output_path)
    return {
        "name": "refresh_risk_evaluation",
        "status": "completed",
        "output_path": str(output_path),
        "model_version": evaluation["model_version"],
        "sample_size": evaluation["sample_size"],
        "roc_auc": evaluation["metrics"]["roc_auc"],
    }


def run_etl(mode: str, *, region: str, log_dir: Path, evaluation_output: Path) -> dict[str, Any]:
    region_config = get_region(region)
    steps: list[dict[str, Any]] = []

    if mode == "sample":
        steps.append(verify_sample_data(region_config.code))
        steps.append(refresh_evaluation(evaluation_output))

    if mode == "live":
        map_key = os.getenv("FIRMS_MAP_KEY")
        if map_key:
            steps.append(run_step([
                sys.executable,
                "scripts/ingest_firms.py",
                "--day-range",
                "3",
                "--region",
                region_config.code,
            ]))
        else:
            steps.append(skipped_step("ingest_firms", "FIRMS_MAP_KEY is not set"))
        steps.append(refresh_evaluation(evaluation_output))

    if mode == "db-refresh":
        if PROCESSED_COUNTIES_PATH.exists():
            steps.append(skipped_step("ingest_counties", "processed county file already exists"))
        else:
            steps.append(run_step([sys.executable, "scripts/ingest_counties.py", "--region", region_config.code]))

        if os.getenv("CENSUS_API_KEY"):
            steps.append(run_step([sys.executable, "scripts/ingest_acs.py", "--region", region_config.code]))
        else:
            steps.append(skipped_step("ingest_acs", "CENSUS_API_KEY is not set; sample exposure will be used"))

        steps.append(run_step([sys.executable, "scripts/load_postgis.py"]))
        steps.append(refresh_evaluation(evaluation_output))

    failed = [step for step in steps if step.get("status") == "failed"]
    run = {
        "mode": mode,
        "region": region_config.code,
        "started_at": steps[0]["started_at"] if steps and "started_at" in steps[0] else utc_now(),
        "finished_at": utc_now(),
        "status": "failed" if failed else "completed",
        "steps": steps,
    }
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"etl_{mode}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    run["log_path"] = str(log_path)
    log_path.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    return run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Wildfire GeoAI ETL workflows.")
    parser.add_argument("--mode", choices=["sample", "live", "db-refresh"], required=True)
    parser.add_argument("--region", default="AZ", help="Region/state code: AZ, CA, NV, NM, TX, CO, or southwest.")
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--evaluation-output", type=Path, default=EVALUATION_PATH)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    run = run_etl(args.mode, region=args.region, log_dir=args.log_dir, evaluation_output=args.evaluation_output)
    print(json.dumps({
        "status": run["status"],
        "mode": run["mode"],
        "region": run["region"],
        "log_path": run["log_path"],
        "steps": [{"status": step["status"], "name": step.get("name") or " ".join(step.get("command", []))} for step in run["steps"]],
    }, indent=2))
    return 1 if run["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())

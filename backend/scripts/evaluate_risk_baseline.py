from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.risk_evaluation import EVALUATION_PATH, write_risk_evaluation


def main() -> None:
    evaluation = write_risk_evaluation()
    metrics = evaluation["metrics"]
    print(f"Wrote risk evaluation: {EVALUATION_PATH}")
    print(
        json.dumps(
            {
                "model_version": evaluation["model_version"],
                "sample_size": evaluation["sample_size"],
                "positive_proxy_count": evaluation["positive_proxy_count"],
                "roc_auc": metrics["roc_auc"],
                "classification": metrics["classification"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

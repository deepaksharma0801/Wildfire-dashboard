from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.data import PROJECT_ROOT
from app.risk import MODEL_VERSION, build_file_risk_grid

EVALUATION_PATH = PROJECT_ROOT / "models" / "risk_baseline_evaluation.json"


def roc_auc(labels: list[int], scores: list[float]) -> float | None:
    positives = sum(labels)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        return None

    ranked = sorted(zip(scores, labels), key=lambda item: item[0])
    rank_sum = 0.0
    index = 0
    while index < len(ranked):
        tie_end = index
        while tie_end + 1 < len(ranked) and ranked[tie_end + 1][0] == ranked[index][0]:
            tie_end += 1
        average_rank = (index + 1 + tie_end + 1) / 2
        for tied_index in range(index, tie_end + 1):
            if ranked[tied_index][1] == 1:
                rank_sum += average_rank
        index = tie_end + 1

    return round((rank_sum - positives * (positives + 1) / 2) / (positives * negatives), 3)


def classification_metrics(labels: list[int], scores: list[float], threshold: float) -> dict[str, Any]:
    tp = fp = tn = fn = 0
    for label, score in zip(labels, scores):
        predicted = score >= threshold
        if predicted and label:
            tp += 1
        elif predicted and not label:
            fp += 1
        elif not predicted and not label:
            tn += 1
        else:
            fn += 1

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    accuracy = (tp + tn) / len(labels) if labels else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    return {
        "threshold": threshold,
        "confusion_matrix": {
            "true_positive": tp,
            "false_positive": fp,
            "true_negative": tn,
            "false_negative": fn,
        },
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "specificity": round(specificity, 3),
        "accuracy": round(accuracy, 3),
        "f1": round(f1, 3),
    }


def top_bucket_capture(labels: list[int], scores: list[float], bucket_fraction: float = 0.25) -> dict[str, Any]:
    ranked = sorted(zip(scores, labels), key=lambda item: item[0], reverse=True)
    bucket_size = max(1, round(len(ranked) * bucket_fraction))
    positives = sum(labels)
    captured = sum(label for _, label in ranked[:bucket_size])
    return {
        "bucket_fraction": bucket_fraction,
        "cell_count": bucket_size,
        "positive_proxy_cells_captured": captured,
        "capture_rate": round(captured / positives, 3) if positives else 0.0,
    }


def build_risk_evaluation(
    *,
    data_source: str = "sample",
    cell_size_deg: float = 1.0,
    decision_threshold: float = 30,
) -> dict[str, Any]:
    grid = build_file_risk_grid(
        data_source=data_source,
        cell_size_deg=cell_size_deg,
        horizon_hours=72,
        min_confidence=0,
    )

    rows = []
    for feature in grid["features"]:
        properties = feature["properties"]
        label = 1 if properties["nearby_detection_count"] > 0 else 0
        rows.append(
            {
                "cell_id": properties["id"],
                "risk_score": properties["risk_score"],
                "label": label,
                "label_reason": "nearby_detection_count_gt_0",
                "recent_activity": properties["recent_activity"],
                "historical_prior": properties["historical_prior"],
                "intensity": properties["intensity"],
                "exposure_proxy": properties["exposure_proxy"],
                "nearby_detection_count": properties["nearby_detection_count"],
            }
        )

    labels = [row["label"] for row in rows]
    scores = [row["risk_score"] for row in rows]

    return {
        "model_version": MODEL_VERSION,
        "evaluation_id": "proxy-grid-backtest-v0.1",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "data_source": data_source,
        "cell_size_deg": cell_size_deg,
        "sample_size": len(rows),
        "positive_proxy_count": sum(labels),
        "negative_proxy_count": len(rows) - sum(labels),
        "label_definition": "A grid cell is positive when at least one sample FIRMS detection is within 50 km of the cell centroid.",
        "metrics": {
            "roc_auc": roc_auc(labels, scores),
            "classification": classification_metrics(labels, scores, decision_threshold),
            "top_quartile_capture": top_bucket_capture(labels, scores),
        },
        "feature_importance_proxy": [
            {"feature": "recent_activity", "weight": 0.45},
            {"feature": "intensity", "weight": 0.25},
            {"feature": "historical_prior", "weight": 0.20},
            {"feature": "exposure_proxy", "weight": 0.10},
        ],
        "rows": rows,
        "limitations": [
            "This is a proxy evaluation against sample detections, not a true historical holdout.",
            "Labels are derived from FIRMS proximity and are not official fire outcomes.",
            "Metrics are useful for diagnostics and portfolio transparency, not operational validation.",
        ],
        "next_steps": [
            "Generate labels from MTBS historical burn perimeters.",
            "Add temporal train/test splits by incident date.",
            "Add spatial holdouts by county or H3 cell.",
            "Train and compare logistic regression and gradient boosting baselines.",
        ],
    }


def load_or_build_risk_evaluation() -> dict[str, Any]:
    if EVALUATION_PATH.exists():
        return json.loads(EVALUATION_PATH.read_text(encoding="utf-8"))
    return build_risk_evaluation()


def write_risk_evaluation(path: Path = EVALUATION_PATH) -> dict[str, Any]:
    evaluation = build_risk_evaluation()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evaluation, indent=2) + "\n", encoding="utf-8")
    return evaluation

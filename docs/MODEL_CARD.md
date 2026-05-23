# Model Card

## Model Name

`baseline-risk-v0.1`

## Intended Use

The model produces a 24-72 hour grid-level wildfire risk score for demo and screening workflows. It is designed to explain how a risk layer might be assembled from geospatial features before a fully evaluated predictive model is added.

## Inputs

- Recent FIRMS detections filtered by date, bounding box, confidence, and data source.
- Detection confidence and fire radiative power.
- Sample historical fire-prior points.
- Nearby population-place proxy.

## Output

Each grid cell receives:

- `risk_score`: 0-100
- `risk_class`: low, moderate, high, or extreme
- `recent_activity`
- `historical_prior`
- `intensity`
- `exposure_proxy`
- `nearby_detection_count`

## Method

The current score is a transparent weighted-distance baseline:

- 45% recent detection activity
- 25% intensity proxy from FRP
- 20% historical fire prior
- 10% nearby population-place exposure proxy

Scores are capped and mapped to classes for visualization.

## Evaluation

Phase 10 adds a proxy evaluation so the dashboard can show diagnostics instead of only a map overlay.

Current proxy evaluation:

- Evaluation id: `proxy-grid-backtest-v0.1`
- Output file: `models/risk_baseline_evaluation.json`
- Endpoint: `GET /api/risk/evaluation`
- Regeneration script: `python scripts/evaluate_risk_baseline.py`
- Label definition: a grid cell is positive when at least one sample FIRMS detection is within 50 km of the cell centroid.

Current sample metrics:

- ROC AUC: 0.975
- Precision at moderate-risk threshold: 0.2
- Recall at moderate-risk threshold: 1.0
- F1 at moderate-risk threshold: 0.333

These metrics are diagnostic only. They are not predictive validation because the labels are derived from sample FIRMS proximity rather than official future fire outcomes.

Required next evaluation steps:

- Replace sample historical priors with MTBS-derived historical burn features.
- Add weather, fuel, land-cover, terrain, and temporal features.
- Use spatial and temporal holdout splits.
- Compare logistic regression, gradient boosting, and calibrated probability outputs.
- Report precision/recall, ROC-AUC, calibration, and spatial error patterns.

## Limitations

- The model can overstate risk near current FIRMS detections because it is detection-driven.
- Current evaluation labels are proxy labels, not official historical burn outcomes.
- It does not yet include wind, humidity, fuels, terrain, lightning, or suppression activity.
- It does not predict spread direction.
- It is not suitable for emergency decision-making.

## Responsible Use

Display caveats wherever generated risk is shown. Treat the layer as a portfolio demonstration of feature engineering and geospatial API design.

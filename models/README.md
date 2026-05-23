# Models

Model work starts after the geospatial application is useful.

- Phase 7: baseline wildfire risk scoring.
- Phase 8: satellite burn scar analysis and segmentation.
- Phase 10: proxy evaluation diagnostics for the baseline risk layer.

Generated artifacts:

- `risk_baseline_evaluation.json`: proxy metrics for `baseline-risk-v0.1`.

Regenerate the evaluation:

```bash
cd backend
source .venv/bin/activate
python scripts/evaluate_risk_baseline.py
```

The current evaluation is intentionally labeled as a proxy backtest. It is useful for demo transparency, not operational validation.

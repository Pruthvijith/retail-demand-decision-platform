"""Backtest one-day-ahead demand using strictly lagged historical features."""

import json
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

from retail_decisions.policy import fit_buffer, policy_replay
from retail_decisions.warehouse import connect

FEATURE_NAMES = ["lag_1", "lag_7", "rolling_7", "weekday", "promo_planned", "price_eur"]


@dataclass(frozen=True)
class Evaluation:
    mae: float
    wmape: float
    bias: float
    n: int


def evaluate(actual: np.ndarray, predicted: np.ndarray) -> Evaluation:
    """wMAPE denominator is actual volume. Bias is signed (prediction-actual)."""
    if len(actual) == 0 or len(actual) != len(predicted):
        raise ValueError("Prediction and target arrays must be nonempty and equal length")
    denominator = float(np.sum(np.abs(actual)))
    if denominator == 0:
        raise ValueError("wMAPE undefined when aggregate actual demand is zero")
    return Evaluation(float(mean_absolute_error(actual, predicted)),
                      float(np.sum(np.abs(actual - predicted)) / denominator),
                      float(np.mean(predicted - actual)), len(actual))


def train_and_backtest(db_path: str, output: str, seed: int = 7) -> dict:
    with connect(db_path) as db:
        # Exclude stockouts, which censor true demand. Lag features may still contain
        # censored history, a documented remaining limitation.
        rows = db.execute(
            """SELECT * FROM daily_features WHERE lag_7 IS NOT NULL AND is_stockout=0
               ORDER BY day,store_id,sku"""
        ).fetchall()
    if not rows:
        raise ValueError("Materialize daily features first")
    dates = sorted({r["day"] for r in rows})
    if len(dates) < 70:
        raise ValueError("Need at least 70 usable days for time-based splits")
    # 3 chronological partitions, common cutoffs across all store-SKU series.
    train_end, valid_end = dates[-43], dates[-22]
    matrix = np.asarray([[r[name] for name in FEATURE_NAMES] for r in rows], dtype=float)
    y = np.asarray([r["units_sold"] for r in rows], dtype=float)
    days = np.asarray([r["day"] for r in rows])
    t, v, h = days < train_end, (days >= train_end) & (days < valid_end), days >= valid_end
    if not min(t.sum(), v.sum(), h.sum()):
        raise ValueError("Chronological partition empty")
    forest = RandomForestRegressor(n_estimators=80, max_depth=9, min_samples_leaf=4,
                                   n_jobs=1, random_state=seed)
    forest.fit(matrix[t], y[t])
    validation_model = np.maximum(0, forest.predict(matrix[v]))
    validation_baseline = matrix[v, FEATURE_NAMES.index("lag_7")]
    model_score = evaluate(y[v], validation_model)
    baseline_score = evaluate(y[v], validation_baseline)
    champion = "random_forest" if model_score.wmape < baseline_score.wmape else "seasonal_naive"
    # The test set remains untouched until selection is complete.
    test_prediction = (np.maximum(0, forest.predict(matrix[h])) if champion == "random_forest"
                       else matrix[h, FEATURE_NAMES.index("lag_7")])
    test_score = evaluate(y[h], test_prediction)
    seasonal_test = matrix[h, FEATURE_NAMES.index("lag_7")]
    chosen_validation = validation_model if champion == "random_forest" else validation_baseline
    policy = {
        "selected": policy_replay(y[h], test_prediction, fit_buffer(y[v], chosen_validation)),
        "seasonal": policy_replay(y[h], seasonal_test, fit_buffer(y[v], validation_baseline)),
    }
    slices = {}
    for label, flag in [("promotion", 1), ("regular", 0)]:
        subgroup = matrix[h, FEATURE_NAMES.index("promo_planned")] == flag
        if subgroup.any():
            slices[label] = vars(evaluate(y[h][subgroup], test_prediction[subgroup]))
    report = {
        "one_day_inventory_scenario": policy, "test_by_promotion": slices,
        "holdout_seasonal_naive": vars(evaluate(y[h], seasonal_test)),
        "dataset": "synthetic store-SKU daily observed sales",
        "model_version": "retail-forecast-v1",
        "feature_names": FEATURE_NAMES,
        "train_end_exclusive": train_end,
        "validation_end_exclusive": valid_end,
        "test_end_inclusive": dates[-1],
        "row_counts": {"train": int(t.sum()), "validation": int(v.sum()), "test": int(h.sum())},
        "validation_random_forest": vars(model_score),
        "validation_seasonal_naive": vars(baseline_score),
        "selected_champion": champion,
        "holdout_test": vars(test_score),
        "evaluation_scope": "one-step ahead with prior observed sales known; excludes stockout targets",
    }
    path = Path(output)
    path.mkdir(parents=True, exist_ok=True)
    if champion == "random_forest":
        joblib.dump(forest, path / "model.joblib")
    else:
        (path / "model.joblib").unlink(missing_ok=True)
    (path / "backtest.json").write_text(json.dumps(report, indent=2) + "\n")
    return report

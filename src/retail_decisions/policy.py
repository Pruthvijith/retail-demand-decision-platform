"""Compare one-day stocking decisions on identical, uncensored store-SKU days."""

import math
import numpy as np


def policy_replay(actual: np.ndarray, prediction: np.ndarray, safety_units: float,
                  lost_margin: float = 3.0, excess_cost: float = 0.60) -> dict:
    """Independent one-period decisions. Positive leftover stock incurs a terminal cost."""
    if len(actual) == 0 or actual.shape != prediction.shape:
        raise ValueError("Align actuals and predictions by store, SKU and day")
    if not all(np.isfinite(v).all() for v in (actual, prediction)):
        raise ValueError("All observations must be finite")
    if not math.isfinite(safety_units) or min(lost_margin, excess_cost) <= 0:
        raise ValueError("Invalid stocking policy")
    target = np.ceil(np.maximum(0, prediction + safety_units))
    lost = np.maximum(actual-target, 0)
    excess = np.maximum(target-actual, 0)
    return dict(opportunities=len(actual), short_units=int(lost.sum()),
                excess_units=int(excess.sum()), shortage_days=int((lost > 0).sum()),
                assumed_lost_margin_eur=lost_margin, assumed_excess_cost_eur=excess_cost,
                buffer_units=float(safety_units),
                scenario_cost_eur=round(float(lost.sum()*lost_margin + excess.sum()*excess_cost), 2))


def fit_buffer(actual: np.ndarray, forecast: np.ndarray, lost: float = 3.0,
               excess: float = 0.60) -> float:
    """Validation residual quantile for asymmetric underage and overage costs."""
    return float(np.quantile(actual-forecast, lost/(lost+excess), method="higher"))

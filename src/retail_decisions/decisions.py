"""Interpretable inventory reorder advice, not autonomous purchase orders."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Recommendation:
    reorder_point: int
    suggested_order_units: int
    expected_lead_time_demand: float
    approximation: str


def recommend_reorder(forecast_daily_units: float, on_hand_units: int,
                      lead_time_days: int, z_service_factor: float = 1.65) -> Recommendation:
    if forecast_daily_units < 0 or on_hand_units < 0 or lead_time_days < 1 or z_service_factor < 0:
        raise ValueError("Invalid demand, stock, lead-time or service factor")
    lead_demand = forecast_daily_units * lead_time_days
    # For illustration only: Poisson-like independent daily demand, variance ~= mean.
    safety_stock = z_service_factor * math.sqrt(lead_demand)
    reorder_point = math.ceil(lead_demand + safety_stock)
    return Recommendation(reorder_point, max(0, reorder_point - on_hand_units), lead_demand,
                          "Poisson-style independent-demand heuristic, no vendor constraints")

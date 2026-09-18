from typing import List

from app.schemas.response import HourlyPlanEntry


def total_grid(plan: List[HourlyPlanEntry]) -> float:
    return sum(e.grid_kwh for e in plan)


def total_cost(plan: List[HourlyPlanEntry], tariff: List[float]) -> float:
    return sum(e.grid_kwh * tariff[e.hour] for e in plan)


def peak_grid(plan: List[HourlyPlanEntry]) -> float:
    return max((e.grid_kwh for e in plan), default=0.0)
from typing import List, Optional

from app.config import settings
from app.optimizer.model import OptimizerInput, OptimizerSolution
from app.schemas.response import BatteryAction, HourlyPlanEntry


def _r(v: float) -> float:
    return round(float(v), settings.ROUND_DECIMALS)


def convert_to_plan(
    inp: OptimizerInput,
    solution: OptimizerSolution,
) -> List[HourlyPlanEntry]:
    n = settings.HOURS_PER_DAY

    charge = [_r(max(0.0, v)) for v in solution.charge]
    discharge = [_r(max(0.0, v)) for v in solution.discharge]
    solar_used = [
        _r(min(max(0.0, v), inp.effective_solar[h]))
        for h, v in enumerate(solution.solar_used)
    ]
    grid = []
    for h in range(n):
        v = _r(max(0.0, solution.grid[h]))
        if inp.grid_cap[h] is not None:
            v = min(v, inp.grid_cap[h])
        grid.append(v)

    energy: List[float] = []
    prev = inp.initial_energy_kwh
    for h in range(n):
        e = prev + charge[h] - discharge[h]
        e = min(max(e, inp.reserve[h]), inp.capacity_kwh)
        energy.append(e)
        prev = e

    plan: List[HourlyPlanEntry] = []
    for h in range(n):
        if charge[h] > 0.0 and discharge[h] <= 0.0:
            action, amount = BatteryAction.CHARGE, charge[h]
        elif discharge[h] > 0.0 and charge[h] <= 0.0:
            action, amount = BatteryAction.DISCHARGE, discharge[h]
        else:
            action, amount = BatteryAction.IDLE, 0.0
        plan.append(
            HourlyPlanEntry(
                hour=h,
                grid_kwh=grid[h],
                solar_used_kwh=solar_used[h],
                battery_action=action,
                battery_kwh=amount,
                battery_energy_after_kwh=energy[h],
            )
        )
    return plan
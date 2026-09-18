from typing import List

from app.directives.compiler import CompiledConstraints
from app.optimizer.converter import convert_to_plan
from app.optimizer.model import OptimizerInput
from app.schemas.request import OptimizeRequest
from app.validation.invariants import check_plan, ValidationReport

ENERGY_TOLERANCE = 0.01
COST_TOLERANCE = 0.01


def replay_plan(
    request: OptimizeRequest,
    compiled: CompiledConstraints,
    plan,
) -> List[str]:
    """Return a list of violation messages for a concrete plan."""
    if hasattr(plan, "hourly_plan"):
        plan = plan.hourly_plan
    rep = check_plan(
        plan,
        demand=request.demand(),
        effective_solar=compiled.effective_solar,
        reserve=compiled.reserve,
        capacity=request.battery.capacity_kwh,
        initial_energy=request.battery.initial_energy_kwh,
        max_charge=request.battery.max_charge_kwh_per_hour,
        max_discharge=request.battery.max_discharge_kwh_per_hour,
        charge_allowed=compiled.charge_allowed,
        discharge_allowed=compiled.discharge_allowed,
        grid_cap=compiled.grid_cap,
    )
    return rep.errors


def check_consistency(
    request: OptimizeRequest,
    plan,
    total_grid: float,
    total_cost: float,
    peak: float,
) -> List[str]:
    errors: List[str] = []
    if hasattr(plan, "hourly_plan"):
        from app.validation.statistics import total_grid as _tg
        from app.validation.statistics import total_cost as _tc
        from app.validation.statistics import peak_grid as _pk

        entries = plan.hourly_plan
        if abs(_tg(entries) - total_grid) > COST_TOLERANCE:
            errors.append("total_grid_kwh inconsistent with hourly_plan")
        if abs(_tc(entries, request.tariff()) - total_cost) > COST_TOLERANCE:
            errors.append("total_cost_bdt inconsistent with hourly_plan")
        if abs(_pk(entries) - peak) > COST_TOLERANCE:
            errors.append("peak_grid_kwh inconsistent with hourly_plan")
    return errors
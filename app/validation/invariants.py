from typing import List, Optional

from app.config import settings
from app.schemas.response import BatteryAction, HourlyPlanEntry


class ValidationReport:
    def __init__(self, ok: bool, errors: Optional[List[str]] = None):
        self.ok = ok
        self.errors = errors or []

    def add(self, cond: bool, msg: str, tol: Optional[float] = None):
        if not cond:
            self.ok = False
            suffix = f" (tolerance {tol})" if tol is not None else ""
            self.errors.append(msg + suffix)

    @property
    def summary(self) -> str:
        return "; ".join(self.errors) if self.errors else "ok"


def near(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol


def check_plan(
    plan: List[HourlyPlanEntry],
    *,
    demand: List[float],
    effective_solar: List[float],
    reserve: List[float],
    capacity: float,
    initial_energy: float,
    max_charge: float,
    max_discharge: float,
    charge_allowed: Optional[List[bool]] = None,
    discharge_allowed: Optional[List[bool]] = None,
    grid_cap: Optional[List[Optional[float]]] = None,
) -> ValidationReport:
    """Highest-fidelity independent replay of a returned schedule.

    Every check mirrors Section 11 of the problem statement. Values are
    compared with the official 0.01 tolerance.
    """
    rep = ValidationReport(True)
    tol = settings.ENERGY_TOLERANCE
    n = settings.HOURS_PER_DAY
    if charge_allowed is None:
        charge_allowed = [True] * n
    if discharge_allowed is None:
        discharge_allowed = [True] * n
    if grid_cap is None:
        grid_cap = [None] * n

    if len(plan) != n:
        rep.add(False, f"hourly_plan must have {n} entries, got {len(plan)}")
        return rep

    hours = [e.hour for e in plan]
    rep.add(sorted(hours) == list(range(n)), "plan hours must be 0..23 unique")

    for e in plan:
        rep.add(e.grid_kwh >= -tol, f"grid negative at hour {e.hour}")
        rep.add(
            e.solar_used_kwh >= -tol, f"solar_used negative at hour {e.hour}"
        )
        rep.add(
            e.battery_energy_after_kwh >= -tol,
            f"battery energy negative at hour {e.hour}",
        )
        rep.add(e.battery_kwh >= -tol, f"battery_kwh negative at hour {e.hour}")
        rep.add(
            e.battery_action in BatteryAction,
            f"invalid battery_action at hour {e.hour}",
        )
        if e.battery_action is BatteryAction.IDLE:
            rep.add(
                near(e.battery_kwh, 0.0, tol),
                f"battery_kwh must be 0 for idle at hour {e.hour}",
            )
        else:
            rep.add(
                e.battery_kwh > 0, f"battery_kwh must be >0 at hour {e.hour}"
            )

    prev = initial_energy
    for h in range(n):
        e = plan[h]
        su_eff = effective_solar[h]
        eff = max(su_eff, 0.0) if su_eff is not None else 0.0

        rep.add(
            e.solar_used_kwh <= eff + tol,
            f"solar_used exceeds effective solar at hour {h}",
            tol,
        )

        action_amount = (
            e.battery_kwh if e.battery_action is not BatteryAction.IDLE else 0.0
        )
        if e.battery_action is BatteryAction.CHARGE:
            rep.add(
                action_amount <= max_charge + tol,
                f"charge exceeds rate limit at hour {h}",
                tol,
            )
            rep.add(
                near(e.battery_energy_after_kwh, prev + action_amount, tol),
                f"charge transition wrong at hour {h}",
                tol,
            )
        elif e.battery_action is BatteryAction.DISCHARGE:
            rep.add(
                action_amount <= max_discharge + tol,
                f"discharge exceeds rate limit at hour {h}",
                tol,
            )
            rep.add(
                near(e.battery_energy_after_kwh, prev - action_amount, tol),
                f"discharge transition wrong at hour {h}",
                tol,
            )
        else:
            rep.add(
                near(e.battery_energy_after_kwh, prev, tol),
                f"idle transition wrong at hour {h}",
                tol,
            )

        rep.add(
            e.battery_energy_after_kwh >= reserve[h] - tol,
            f"battery below reserve at hour {h}",
            tol,
        )
        rep.add(
            e.battery_energy_after_kwh <= capacity + tol,
            f"battery above capacity at hour {h}",
            tol,
        )

        if charge_allowed[h] is False:
            rep.add(
                near(e.battery_charge_kwh, 0.0, tol),
                f"no_charge_window violated at hour {h}",
                tol,
            )
        if discharge_allowed[h] is False:
            rep.add(
                near(e.battery_discharge_kwh, 0.0, tol),
                f"no_discharge_window violated at hour {h}",
                tol,
            )
        if grid_cap[h] is not None:
            rep.add(
                e.grid_kwh <= grid_cap[h] + tol,
                f"grid exceeds cap at hour {h}",
                tol,
            )

        rep.add(
            near(
                e.grid_kwh + e.solar_used_kwh + e.battery_discharge_kwh,
                demand[h] + e.battery_charge_kwh,
                tol,
            ),
            f"energy balance violated at hour {h}",
            tol,
        )
        prev = e.battery_energy_after_kwh

    rep.add(
        near(prev, initial_energy, tol),
        "final battery energy must equal initial energy",
        tol,
    )
    return rep
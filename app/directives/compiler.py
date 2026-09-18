from typing import List, Optional

from app.config import settings
from app.directives.types import Directive, DirectiveType


def _area(hours: List[int]) -> set:
    return set(hours)


class CompiledConstraints:
    """Merged constraint arrays consumed by the optimizer."""

    def __init__(self):
        self.effective_solar: List[float] = []
        self.reserve: List[float] = []
        self.charge_allowed: List[bool] = []
        self.discharge_allowed: List[bool] = []
        self.grid_cap: List[Optional[float]] = []

    @classmethod
    def build(
        cls,
        base_solar: List[float],
        base_minimum_energy: float,
        directives: List[Directive],
    ) -> "CompiledConstraints":
        c = cls()
        n = settings.HOURS_PER_DAY

        factor_by_hour = [1.0] * n
        reserve_by_hour = [base_minimum_energy] * n
        charge_allowed = [True] * n
        discharge_allowed = [True] * n
        grid_cap = [None] * n

        for d in directives:
            if d.directive_type is DirectiveType.NO_OP:
                continue
            hours = _area(d.hours)
            if d.directive_type is DirectiveType.SOLAR_REDUCTION:
                for h in hours:
                    factor_by_hour[h] *= d.factor
            elif d.directive_type is DirectiveType.MINIMUM_BATTERY_RESERVE:
                for h in hours:
                    reserve_by_hour[h] = max(
                        reserve_by_hour[h], d.minimum_energy_kwh
                    )
            elif d.directive_type is DirectiveType.NO_CHARGE_WINDOW:
                for h in hours:
                    charge_allowed[h] = False
            elif d.directive_type is DirectiveType.NO_DISCHARGE_WINDOW:
                for h in hours:
                    discharge_allowed[h] = False
            elif d.directive_type is DirectiveType.MAX_GRID_WINDOW:
                for h in hours:
                    grid_cap[h] = (
                        d.max_grid_kwh
                        if grid_cap[h] is None
                        else min(grid_cap[h], d.max_grid_kwh)
                    )

        c.effective_solar = [
            base_solar[h] * factor_by_hour[h] for h in range(n)
        ]
        c.reserve = reserve_by_hour
        c.charge_allowed = charge_allowed
        c.discharge_allowed = discharge_allowed
        c.grid_cap = grid_cap
        return c
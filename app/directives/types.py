from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class DirectiveType(str, Enum):
    SOLAR_REDUCTION = "solar_reduction"
    MINIMUM_BATTERY_RESERVE = "minimum_battery_reserve"
    NO_CHARGE_WINDOW = "no_charge_window"
    NO_DISCHARGE_WINDOW = "no_discharge_window"
    MAX_GRID_WINDOW = "max_grid_window"
    NO_OP = "no_op"

    @classmethod
    def has_value(cls, value: str) -> bool:
        return any(value == v.value for v in cls)


@dataclass
class Directive:
    note_index: int
    directive_type: DirectiveType
    applies: bool
    hours: List[int] = field(default_factory=list)
    factor: Optional[float] = None
    minimum_energy_kwh: Optional[float] = None
    max_grid_kwh: Optional[float] = None
    explanation: str = ""

    @property
    def structured_adjustment(self) -> Optional[dict]:
        if self.directive_type is DirectiveType.NO_OP:
            return None
        if self.directive_type is DirectiveType.SOLAR_REDUCTION:
            return {"hours": list(self.hours), "factor": self.factor}
        if self.directive_type is DirectiveType.MINIMUM_BATTERY_RESERVE:
            return {
                "hours": list(self.hours),
                "minimum_energy_kwh": self.minimum_energy_kwh,
            }
        if self.directive_type in (
            DirectiveType.NO_CHARGE_WINDOW,
            DirectiveType.NO_DISCHARGE_WINDOW,
        ):
            return {"hours": list(self.hours)}
        if self.directive_type is DirectiveType.MAX_GRID_WINDOW:
            return {"hours": list(self.hours), "max_grid_kwh": self.max_grid_kwh}
        return None
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class BatteryAction(str, Enum):
    CHARGE = "charge"
    DISCHARGE = "discharge"
    IDLE = "idle"


class HourlyPlanEntry(BaseModel):
    hour: int
    grid_kwh: float = Field(ge=0)
    solar_used_kwh: float = Field(ge=0)
    battery_action: BatteryAction
    battery_kwh: float = Field(ge=0)
    battery_energy_after_kwh: float = Field(ge=0)

    @property
    def battery_discharge_kwh(self) -> float:
        return self.battery_kwh if self.battery_action is BatteryAction.DISCHARGE else 0.0

    @property
    def battery_charge_kwh(self) -> float:
        return self.battery_kwh if self.battery_action is BatteryAction.CHARGE else 0.0


class DirectiveInterpretation(BaseModel):
    note_index: int = Field(ge=0)
    applies: bool
    directive_type: str
    structured_adjustment: Optional[dict] = None
    explanation: str = ""


class OptimizationResponse(BaseModel):
    scenario_id: str
    directive_interpretation: List[DirectiveInterpretation]
    hourly_plan: List[HourlyPlanEntry] = Field(min_length=24, max_length=24)
    total_grid_kwh: float = Field(ge=0)
    total_cost_bdt: float = Field(ge=0)
    peak_grid_kwh: float = Field(ge=0)
    plan_summary: str = ""


class HealthResponse(BaseModel):
    status: str
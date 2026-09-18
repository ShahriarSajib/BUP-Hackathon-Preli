from typing import List

from pydantic import BaseModel, Field, field_validator, model_validator

from app.config import settings


class HourInput(BaseModel):
    hour: int
    demand_kwh: float = Field(ge=0)
    solar_kwh: float = Field(ge=0)
    tariff_bdt_per_kwh: float = Field(ge=0)


class BatteryInput(BaseModel):
    capacity_kwh: float = Field(gt=0)
    initial_energy_kwh: float = Field(ge=0)
    minimum_energy_kwh: float = Field(ge=0)
    max_charge_kwh_per_hour: float = Field(ge=0)
    max_discharge_kwh_per_hour: float = Field(ge=0)

    @model_validator(mode="after")
    def _check_bounds(self) -> "BatteryInput":
        if self.minimum_energy_kwh > self.capacity_kwh:
            raise ValueError(
                "battery.minimum_energy_kwh cannot exceed battery.capacity_kwh"
            )
        if self.initial_energy_kwh < self.minimum_energy_kwh:
            raise ValueError(
                "battery.initial_energy_kwh cannot be below battery.minimum_energy_kwh"
            )
        if self.initial_energy_kwh > self.capacity_kwh:
            raise ValueError(
                "battery.initial_energy_kwh cannot exceed battery.capacity_kwh"
            )
        return self


class OptimizeRequest(BaseModel):
    scenario_id: str = Field(min_length=1)
    operator_notes: List[str] = Field(min_length=1, max_length=3)
    hours: List[HourInput] = Field(min_length=24, max_length=24)
    battery: BatteryInput

    @field_validator("operator_notes")
    @classmethod
    def _notes_non_empty(cls, v: List[str]) -> List[str]:
        for note in v:
            if not note.strip():
                raise ValueError("operator_notes entries must be non-empty strings")
        return v

    @model_validator(mode="after")
    def _check_hours(self) -> "OptimizeRequest":
        if len(self.hours) != settings.HOURS_PER_DAY:
            raise ValueError("hours must contain exactly 24 entries")
        seen = {h.hour for h in self.hours}
        if len(seen) != settings.HOURS_PER_DAY:
            raise ValueError("hour values must be unique")
        if min(seen) != 0 or max(seen) != settings.HOURS_PER_DAY - 1:
            raise ValueError("hour values must cover exactly 0 through 23")
        return self

    def sorted_hours(self):
        return sorted(self.hours, key=lambda h: h.hour)

    def demand(self):
        return [h.demand_kwh for h in self.sorted_hours()]

    def solar(self):
        return [h.solar_kwh for h in self.sorted_hours()]

    def tariff(self):
        return [h.tariff_bdt_per_kwh for h in self.sorted_hours()]
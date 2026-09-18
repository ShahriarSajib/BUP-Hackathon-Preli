from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class OptimizerInput:
    demand: List[float]
    base_solar: List[float]
    tariff: List[float]
    effective_solar: List[float]
    reserve: List[float]
    charge_allowed: List[bool]
    discharge_allowed: List[bool]
    grid_cap: List[Optional[float]]
    capacity_kwh: float
    initial_energy_kwh: float
    max_charge_kwh: float
    max_discharge_kwh: float


@dataclass
class OptimizerSolution:
    grid: List[float]
    solar_used: List[float]
    charge: List[float]
    discharge: List[float]
    energy: List[float]
    feasible: bool
    solver_status: Optional[str] = None
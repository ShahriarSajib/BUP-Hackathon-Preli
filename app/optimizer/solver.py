from typing import List, Optional

from ortools.linear_solver import pywraplp

from app.config import settings
from app.optimizer.model import OptimizerInput, OptimizerSolution

_STATUS_NAMES = {
    pywraplp.Solver.OPTIMAL: "OPTIMAL",
    pywraplp.Solver.FEASIBLE: "FEASIBLE",
    pywraplp.Solver.INFEASIBLE: "INFEASIBLE",
    pywraplp.Solver.UNBOUNDED: "UNBOUNDED",
    pywraplp.Solver.ABNORMAL: "ABNORMAL",
    pywraplp.Solver.MODEL_INVALID: "MODEL_INVALID",
    pywraplp.Solver.NOT_SOLVED: "NOT_SOLVED",
}


def _solver(name: str) -> Optional[pywraplp.Solver]:
    try:
        solver = pywraplp.Solver.CreateSolver(name)
        if solver:
            return solver
    except Exception:
        return None
    for fallback in ("CBC", "SCIP", "GLOP"):
        try:
            solver = pywraplp.Solver.CreateSolver(fallback)
            if solver:
                return solver
        except Exception:
            continue
    return None


def solve(inp: OptimizerInput) -> OptimizerSolution:
    n = settings.HOURS_PER_DAY
    solver = _solver(settings.OPTIMIZER_SOLVER)
    if solver is None:
        return OptimizerSolution(
            grid=[], solar_used=[], charge=[], discharge=[], energy=[],
            feasible=False, solver_status="NO_SOLVER",
        )

    inf = solver.infinity()
    grid = [solver.NumVar(0, inf, f"grid_{h}") for h in range(n)]
    solar_used = [
        solver.NumVar(0, max(0.0, inp.effective_solar[h]), f"su_{h}")
        for h in range(n)
    ]
    charge = [
        solver.NumVar(
            0, inp.max_charge_kwh if inp.charge_allowed[h] else 0.0, f"ch_{h}"
        )
        for h in range(n)
    ]
    discharge = [
        solver.NumVar(
            0,
            inp.max_discharge_kwh if inp.discharge_allowed[h] else 0.0,
            f"dc_{h}",
        )
        for h in range(n)
    ]
    energy = [
        solver.NumVar(inp.reserve[h], inp.capacity_kwh, f"en_{h}")
        for h in range(n)
    ]
    charge_mode = [solver.BoolVar(f"cm_{h}") for h in range(n)]
    discharge_mode = [solver.BoolVar(f"dm_{h}") for h in range(n)]

    for h in range(n):
        if inp.charge_allowed[h]:
            solver.Add(charge[h] <= inp.max_charge_kwh * charge_mode[h])
        else:
            solver.Add(charge_mode[h] == 0)
        if inp.discharge_allowed[h]:
            solver.Add(
                discharge[h] <= inp.max_discharge_kwh * discharge_mode[h]
            )
        else:
            solver.Add(discharge_mode[h] == 0)
        solver.Add(charge_mode[h] + discharge_mode[h] <= 1)

        prev = inp.initial_energy_kwh if h == 0 else energy[h - 1]
        solver.Add(energy[h] == prev + charge[h] - discharge[h])

        solver.Add(
            grid[h] + solar_used[h] + discharge[h]
            == inp.demand[h] + charge[h]
        )
        if inp.grid_cap[h] is not None:
            solver.Add(grid[h] <= inp.grid_cap[h])

    solver.Add(energy[n - 1] == inp.initial_energy_kwh)

    objective = solver.Sum(
        grid[h] * inp.tariff[h] for h in range(n)
    )
    solver.Minimize(objective)
    solver.SetTimeLimit(int(settings.OPTIMIZER_TIME_LIMIT_SECONDS * 1000))

    status = solver.Solve()
    feasible = status in (
        pywraplp.Solver.OPTIMAL,
        pywraplp.Solver.FEASIBLE,
    )
    if not feasible:
        return OptimizerSolution(
            grid=[], solar_used=[], charge=[], discharge=[], energy=[],
            feasible=False, solver_status=_STATUS_NAMES.get(status, 'UNKNOWN'),
        )

    return OptimizerSolution(
        grid=[grid[h].solution_value() for h in range(n)],
        solar_used=[solar_used[h].solution_value() for h in range(n)],
        charge=[charge[h].solution_value() for h in range(n)],
        discharge=[discharge[h].solution_value() for h in range(n)],
        energy=[energy[h].solution_value() for h in range(n)],
        feasible=True,
        solver_status=_STATUS_NAMES.get(status, 'UNKNOWN'),
    )
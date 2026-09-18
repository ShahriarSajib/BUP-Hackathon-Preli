from app.directives.compiler import CompiledConstraints
from app.optimizer.converter import convert_to_plan
from app.optimizer.model import OptimizerInput
from app.optimizer.solver import solve
from app.validation.invariants import check_plan

N = 24


def _make_input(demand, solar, tariff, **overrides):
    bat = {
        "capacity_kwh": 200, "initial_energy_kwh": 100,
        "minimum_energy_kwh": 40, "max_charge_kwh": 60,
        "max_discharge_kwh": 60,
        **{k: v for k, v in overrides.items() if k in (
            "capacity_kwh", "initial_energy_kwh", "minimum_energy_kwh",
            "max_charge_kwh", "max_discharge_kwh",
        )},
    }
    eff_solar = overrides.get("effective_solar", solar[:])
    reserve = overrides.get("reserve", [bat["minimum_energy_kwh"]] * N)
    charge_allowed = overrides.get("charge_allowed", [True] * N)
    discharge_allowed = overrides.get("discharge_allowed", [True] * N)
    grid_cap = overrides.get("grid_cap", [None] * N)
    return OptimizerInput(
        demand=demand, base_solar=solar, tariff=tariff,
        effective_solar=eff_solar, reserve=reserve,
        charge_allowed=charge_allowed, discharge_allowed=discharge_allowed,
        grid_cap=grid_cap,
        capacity_kwh=bat["capacity_kwh"],
        initial_energy_kwh=bat["initial_energy_kwh"],
        max_charge_kwh=bat["max_charge_kwh"],
        max_discharge_kwh=bat["max_discharge_kwh"],
    )


def _validate(inp, solution, **overrides):
    plan = convert_to_plan(inp, solution)
    rep = check_plan(
        plan,
        demand=inp.demand,
        effective_solar=overrides.get("effective_solar", inp.effective_solar),
        reserve=overrides.get("reserve", inp.reserve),
        capacity=inp.capacity_kwh,
        initial_energy=inp.initial_energy_kwh,
        max_charge=inp.max_charge_kwh,
        max_discharge=inp.max_discharge_kwh,
        charge_allowed=overrides.get("charge_allowed", inp.charge_allowed),
        discharge_allowed=overrides.get("discharge_allowed", inp.discharge_allowed),
        grid_cap=overrides.get("grid_cap", inp.grid_cap),
    )
    return rep


def test_no_solar_all_grid():
    demand = [100] * 24
    solar = [0] * 24
    tariff = [10] * 24
    inp = _make_input(demand, solar, tariff)
    sol = solve(inp)
    assert sol.feasible
    assert sum(sol.grid) >= sum(demand) - 10  # at least covers demand (battery shift)
    rep = _validate(inp, sol)
    assert rep.ok, rep.summary


def test_solar_covers_demand():
    demand = [50] * 24
    solar = [50] * 24
    tariff = [10] * 24
    inp = _make_input(demand, solar, tariff)
    sol = solve(inp)
    assert sol.feasible
    rep = _validate(inp, sol)
    assert rep.ok, rep.summary
    assert sum(sol.grid) < 10


def test_cheap_nighttime_charging():
    demand = [100] * 24
    solar = [0] * 24
    tariff = [5] * 12 + [20] * 12
    inp = _make_input(demand, solar, tariff)
    sol = solve(inp)
    assert sol.feasible
    rep = _validate(inp, sol)
    assert rep.ok, rep.summary
    assert sum(sol.charge[:12]) > 30


def test_grid_cap_respected():
    demand = [60] * 24
    demand[18] = 180
    demand[19] = 180
    solar = [0] * 24
    tariff = [10] * 24
    grid_cap = [None] * 24
    grid_cap[18] = 120
    grid_cap[19] = 120
    inp = _make_input(
        demand, solar, tariff, grid_cap=grid_cap,
        initial_energy_kwh=100, max_charge_kwh=60, max_discharge_kwh=60,
    )
    sol = solve(inp)
    assert sol.feasible, sol.solver_status
    rep = _validate(inp, sol, grid_cap=grid_cap)
    assert rep.ok, rep.summary
    assert sol.grid[18] <= 120.1
    assert sol.grid[19] <= 120.1


def test_no_charge_window():
    demand = [100] * 24
    solar = [0] * 24
    tariff = [5] * 24
    charge_allowed = [False] * 12 + [True] * 12
    inp = _make_input(
        demand, solar, tariff,
        charge_allowed=charge_allowed,
        initial_energy_kwh=100, max_charge_kwh=60,
    )
    sol = solve(inp)
    assert sol.feasible
    rep = _validate(inp, sol, charge_allowed=charge_allowed)
    assert rep.ok, rep.summary
    assert all(v == 0 for v in sol.charge[:12])


def test_no_discharge_window():
    demand = [100] * 24
    solar = [0] * 24
    tariff = [20] * 24
    discharge_allowed = [True] * 12 + [False] * 12
    inp = _make_input(
        demand, solar, tariff, discharge_allowed=discharge_allowed,
        max_discharge_kwh=60,
    )
    sol = solve(inp)
    assert sol.feasible
    rep = _validate(inp, sol, discharge_allowed=discharge_allowed)
    assert rep.ok, rep.summary
    assert all(v == 0 for v in sol.discharge[12:])


def test_reserve_respected():
    demand = [200] * 24
    solar = [0] * 24
    tariff = [10] * 24
    reserve = [40] * 24
    reserve[18] = 150
    reserve[19] = 150
    inp = _make_input(demand, solar, tariff, reserve=reserve)
    sol = solve(inp)
    assert sol.feasible
    rep = _validate(inp, sol, reserve=reserve)
    assert rep.ok, rep.summary
    assert sol.energy[18] >= 149.99
    assert sol.energy[19] >= 149.99


def test_no_simultaneous_charge_discharge():
    import random
    random.seed(7)
    demand = [random.randint(50, 250) for _ in range(24)]
    solar = [random.randint(0, 150) for _ in range(24)]
    tariff = [random.randint(1, 30) for _ in range(24)]
    inp = _make_input(demand, solar, tariff)
    sol = solve(inp)
    assert sol.feasible
    for h in range(24):
        assert not (sol.charge[h] > 0.001 and sol.discharge[h] > 0.001), h


def test_final_battery_neutrality():
    import random
    random.seed(11)
    demand = [random.randint(60, 240) for _ in range(24)]
    solar = [random.randint(0, 120) for _ in range(24)]
    tariff = [random.randint(1, 30) for _ in range(24)]
    inp = _make_input(demand, solar, tariff)
    sol = solve(inp)
    assert sol.feasible
    assert abs(sol.energy[23] - inp.initial_energy_kwh) < 0.01
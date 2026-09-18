import random

from app.directives.compiler import CompiledConstraints
from app.directives.types import Directive, DirectiveType
from app.optimizer.converter import convert_to_plan
from app.optimizer.model import OptimizerInput
from app.optimizer.solver import solve
from app.validation.invariants import check_plan


def test_random_feasible_scenarios_replay_cleanly():
    rng = random.Random(2026)
    failures = []
    for trial in range(200):
        n = 24
        capacity = rng.choice([150, 220, 300, 500])
        max_charge = rng.randint(30, 90)
        max_discharge = rng.randint(30, 90)
        initial = rng.randint(60, capacity)
        base_min = rng.randint(0, min(60, capacity))

        demand = [rng.randint(50, 300) for _ in range(n)]
        solar = [rng.randint(0, 180) for _ in range(n)]
        tariff = [rng.randint(1, 35) for _ in range(n)]

        directives = []
        # solar reduction on a random window
        s0 = rng.randint(8, 15)
        s1 = rng.randint(s0 + 1, min(s0 + 4, 24))
        directives.append(
            Directive(
                note_index=0,
                directive_type=DirectiveType.SOLAR_REDUCTION,
                applies=True,
                hours=list(range(s0, s1)),
                factor=round(rng.uniform(0.1, 0.9), 2),
            )
        )
        if rng.random() < 0.5:
            c0 = rng.randint(9, 15)
            c1 = rng.randint(c0 + 1, min(c0 + 3, 24))
            directives.append(
                Directive(
                    note_index=1,
                    directive_type=DirectiveType.NO_CHARGE_WINDOW,
                    applies=True,
                    hours=list(range(c0, c1)),
                )
            )
        if rng.random() < 0.5:
            d0 = rng.randint(9, 17)
            d1 = rng.randint(d0 + 1, min(d0 + 3, 24))
            directives.append(
                Directive(
                    note_index=2,
                    directive_type=DirectiveType.NO_DISCHARGE_WINDOW,
                    applies=True,
                    hours=list(range(d0, d1)),
                )
            )

        compiled = CompiledConstraints.build(solar, base_min, directives)
        inp = OptimizerInput(
            demand=demand, base_solar=solar, tariff=tariff,
            effective_solar=compiled.effective_solar,
            reserve=compiled.reserve,
            charge_allowed=compiled.charge_allowed,
            discharge_allowed=compiled.discharge_allowed,
            grid_cap=compiled.grid_cap,
            capacity_kwh=capacity, initial_energy_kwh=initial,
            max_charge_kwh=max_charge, max_discharge_kwh=max_discharge,
        )
        sol = solve(inp)
        if not sol.feasible:
            failures.append((trial, sol.solver_status))
            continue
        plan = convert_to_plan(inp, sol)
        rep = check_plan(
            plan,
            demand=demand, effective_solar=compiled.effective_solar,
            reserve=compiled.reserve, capacity=capacity,
            initial_energy=initial, max_charge=max_charge,
            max_discharge=max_discharge,
            charge_allowed=compiled.charge_allowed,
            discharge_allowed=compiled.discharge_allowed,
            grid_cap=compiled.grid_cap,
        )
        if not rep.ok:
            failures.append((trial, rep.summary))

    assert not failures, f"{len(failures)} failures: {failures[:5]}"
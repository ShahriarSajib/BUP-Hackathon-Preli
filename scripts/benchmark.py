import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.directives.compiler import CompiledConstraints
from app.interpreter.router import InterpreterRouter
from app.optimizer.model import OptimizerInput
from app.optimizer.solver import solve
from app.schemas.request import OptimizeRequest
from app.services.optimization_service import OptimizationService
from app.validation.invariants import check_plan

PUBLIC_CASES = (
    Path(__file__).resolve().parents[1] / "BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"
)


def _percentile(values, p):
    values = sorted(values)
    if not values:
        return 0.0
    k = (len(values) - 1) * p / 100.0
    f = int(k)
    c = min(f + 1, len(values) - 1)
    return values[f] + (values[c] - values[f]) * (k - f)


def report(name, values):
    if not values:
        print(f"{name:28s} n=0")
        return
    print(
        f"{name:28s} n={len(values):3d}  p50={_percentile(values,50)*1000:7.2f}ms "
        f"p95={_percentile(values,95)*1000:7.2f}ms p99={_percentile(values,99)*1000:7.2f}ms "
        f"max={max(values)*1000:7.2f}ms"
    )


def main():
    data = json.load(open(PUBLIC_CASES))
    cases = data["cases"]
    requests = [OptimizeRequest(**c["input"]) for c in cases]
    n_iter = int(sys.argv[1]) if len(sys.argv) > 1 else 20

    total_times = []
    solver_times = []
    llm_times = []
    replay_times = []

    router = InterpreterRouter()
    service = OptimizationService(interpreter=router)

    for _ in range(n_iter):
        for request in requests:
            t0 = time.perf_counter()

            t0l = time.perf_counter()
            semantic = router.interpret(request.operator_notes, request.battery.capacity_kwh)
            llm_times.append(time.perf_counter() - t0l)

            from app.directives.validator import build_directive_from_semantic
            directives = [
                build_directive_from_semantic(s, len(request.operator_notes), request.battery.capacity_kwh)
                for s in semantic
            ]
            compiled = CompiledConstraints.build(
                request.solar(), request.battery.minimum_energy_kwh, directives
            )
            inp = OptimizerInput(
                demand=request.demand(), base_solar=request.solar(), tariff=request.tariff(),
                effective_solar=compiled.effective_solar, reserve=compiled.reserve,
                charge_allowed=compiled.charge_allowed,
                discharge_allowed=compiled.discharge_allowed, grid_cap=compiled.grid_cap,
                capacity_kwh=request.battery.capacity_kwh,
                initial_energy_kwh=request.battery.initial_energy_kwh,
                max_charge_kwh=request.battery.max_charge_kwh_per_hour,
                max_discharge_kwh=request.battery.max_discharge_kwh_per_hour,
            )
            t0s = time.perf_counter()
            solution = solve(inp)
            solver_times.append(time.perf_counter() - t0s)

            from app.optimizer.converter import convert_to_plan
            plan = convert_to_plan(inp, solution)

            t0r = time.perf_counter()
            rep = check_plan(
                plan, demand=request.demand(), effective_solar=compiled.effective_solar,
                reserve=compiled.reserve, capacity=request.battery.capacity_kwh,
                initial_energy=request.battery.initial_energy_kwh,
                max_charge=request.battery.max_charge_kwh_per_hour,
                max_discharge=request.battery.max_discharge_kwh_per_hour,
                charge_allowed=compiled.charge_allowed,
                discharge_allowed=compiled.discharge_allowed,
                grid_cap=compiled.grid_cap,
            )
            replay_times.append(time.perf_counter() - t0r)

            total_times.append(time.perf_counter() - t0)
            assert rep.ok, rep.summary

    print(f"ran {n_iter}x over {len(cases)} public scenarios")
    report("total pipeline", total_times)
    report("interpretation", llm_times)
    report("optimizer (solve)", solver_times)
    report("replay validation", replay_times)


if __name__ == "__main__":
    main()
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.directives.compiler import CompiledConstraints
from app.directives.validator import (
    build_directive_from_semantic,
    validate_directives,
)
from app.schemas.request import OptimizeRequest
from app.schemas.response import HourlyPlanEntry
from app.validation.invariants import check_plan
from app.validation.statistics import peak_grid, total_cost, total_grid

TOL = 0.01


def interpret_from_response(request, response):
    directives = []
    for entry in response["directive_interpretation"]:
        sem = {
            "note_index": entry["note_index"],
            "directive_type": entry["directive_type"],
            "applies": entry["applies"],
            "structured_adjustment": entry["structured_adjustment"],
        }
        if sem["directive_type"] == "no_op":
            start = end = factor = kwh = frac = cap = None
        else:
            adj = entry["structured_adjustment"]
            hours = adj["hours"]
            start, end = hours[0], hours[-1] + 1
            factor = adj.get("factor")
            kwh = adj.get("minimum_energy_kwh")
            cap = adj.get("max_grid_kwh")
            frac = None
        directives.append(
            build_directive_from_semantic(
                {
                    "note_index": sem["note_index"],
                    "directive_type": sem["directive_type"],
                    "applies": sem["applies"],
                    "start_hour": start,
                    "end_hour": end,
                    "factor": factor,
                    "minimum_energy_kwh": kwh,
                    "minimum_energy_fraction": frac,
                    "max_grid_kwh": cap,
                },
                len(request.operator_notes),
                request.battery.capacity_kwh,
            )
        )
    return validate_directives(
        directives, len(request.operator_notes), request.battery.capacity_kwh
    )


def score_case(case, response):
    errors = []
    request = OptimizeRequest(**case["input"])
    expected = case["expected_output"]

    if response.get("scenario_id") != request.scenario_id:
        errors.append("scenario_id mismatch")

    got = response.get("directive_interpretation")
    exp = expected["directive_interpretation"]
    if len(got) != len(exp):
        errors.append(f"interpretation count {len(got)} != {len(exp)}")
    else:
        for gi, ei in zip(got, exp):
            if gi["note_index"] != ei["note_index"]:
                errors.append("note_index order mismatch")
            if gi["applies"] != ei["applies"]:
                errors.append(f"applies mismatch for note {gi['note_index']}")
            if gi["directive_type"] != ei["directive_type"]:
                errors.append(
                    f"type {gi['directive_type']} != {ei['directive_type']} "
                    f"for note {gi['note_index']}"
                )
            gj = gi["structured_adjustment"]
            ej = ei["structured_adjustment"]
            if gj is None or ej is None:
                if not (gj is None and ej is None):
                    errors.append(
                        f"structured_adjustment null mismatch note {gi['note_index']}"
                    )
            else:
                if gj.get("hours") != ej.get("hours"):
                    errors.append(
                        f"hours {gj.get('hours')} != {ej.get('hours')} "
                        f"for note {gi['note_index']}"
                    )
                for key in ("factor", "minimum_energy_kwh", "max_grid_kwh"):
                    if key in ej and ej[key] is not None:
                        if gj.get(key) is None or abs(gj.get(key) - ej[key]) > TOL:
                            errors.append(
                                f"{key} {gj.get(key)} != {ej[key]} note {gi['note_index']}"
                            )

    plan_entries = [
        HourlyPlanEntry.model_validate(e) for e in response["hourly_plan"]
    ]
    directives = interpret_from_response(request, response)
    compiled = CompiledConstraints.build(
        request.solar(), request.battery.minimum_energy_kwh, directives
    )
    rep = check_plan(
        plan_entries,
        demand=request.demand(),
        effective_solar=compiled.effective_solar,
        reserve=compiled.reserve,
        capacity=request.battery.capacity_kwh,
        initial_energy=request.battery.initial_energy_kwh,
        max_charge=request.battery.max_charge_kwh_per_hour,
        max_discharge=request.battery.max_discharge_kwh_per_hour,
        charge_allowed=compiled.charge_allowed,
        discharge_allowed=compiled.discharge_allowed,
        grid_cap=compiled.grid_cap,
    )
    if not rep.ok:
        errors.append(f"PLAN INVALID: {rep.summary}")

    tariff = request.tariff()
    actual_cost = total_cost(plan_entries, tariff)
    expected_cost = expected["total_cost_bdt"]
    if actual_cost > expected_cost + TOL:
        errors.append(
            f"cost {actual_cost} exceeds optimal {expected_cost} by {actual_cost - expected_cost}"
        )

    if abs(total_grid(plan_entries) - response["total_grid_kwh"]) > TOL:
        errors.append("total_grid_kwh inconsistent")
    if abs(actual_cost - response["total_cost_bdt"]) > TOL:
        errors.append("total_cost_bdt inconsistent")
    if abs(peak_grid(plan_entries) - response["peak_grid_kwh"]) > TOL:
        errors.append("peak_grid_kwh inconsistent")

    return errors, actual_cost, expected_cost


def main():
    path = (
        sys.argv[1]
        if len(sys.argv) > 1
        else Path(__file__).resolve().parents[1]
        / "BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"
    )
    data = json.load(open(path))
    for case in data["cases"]:
        print(case["id"], "validate a response with score_case(case, response)")


if __name__ == "__main__":
    main()
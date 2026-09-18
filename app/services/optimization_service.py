import logging
from typing import List

from app.config import settings
from app.directives.compiler import CompiledConstraints
from app.directives.types import Directive
from app.directives.validator import (
    build_directive_from_semantic,
    validate_directives,
)
from app.interpreter.router import InterpreterRouter
from app.optimizer.converter import convert_to_plan
from app.optimizer.model import OptimizerInput
from app.optimizer.solver import solve
from app.schemas.request import OptimizeRequest
from app.schemas.response import (
    DirectiveInterpretation,
    OptimizationResponse,
)
from app.validation.invariants import check_plan
from app.validation.statistics import peak_grid, total_cost, total_grid

logger = logging.getLogger(__name__)


class InterpretationError(Exception):
    pass


class OptimizationError(Exception):
    pass


class ValidationError(Exception):
    pass


def _round(v, decimals=None):
    return round(float(v), decimals if decimals is not None else settings.ROUND_DECIMALS)


class OptimizationService:
    def __init__(self, interpreter: InterpreterRouter = None):
        self.interpreter = interpreter or InterpreterRouter()

    def optimize(self, request: OptimizeRequest) -> OptimizationResponse:
        notes = request.operator_notes
        capacity = request.battery.capacity_kwh

        directives = self._interpret_directives(notes, capacity)
        compiled = CompiledConstraints.build(
            request.solar(), request.battery.minimum_energy_kwh, directives
        )

        inp = OptimizerInput(
            demand=request.demand(),
            base_solar=request.solar(),
            tariff=request.tariff(),
            effective_solar=compiled.effective_solar,
            reserve=compiled.reserve,
            charge_allowed=compiled.charge_allowed,
            discharge_allowed=compiled.discharge_allowed,
            grid_cap=compiled.grid_cap,
            capacity_kwh=request.battery.capacity_kwh,
            initial_energy_kwh=request.battery.initial_energy_kwh,
            max_charge_kwh=request.battery.max_charge_kwh_per_hour,
            max_discharge_kwh=request.battery.max_discharge_kwh_per_hour,
        )
        solution = solve(inp)
        if not solution.feasible:
            logger.error("optimizer infeasible: %s", solution.solver_status)
            raise OptimizationError(
                "no feasible schedule satisfies the given constraints"
            )

        plan = convert_to_plan(inp, solution)

        rep = check_plan(
            plan,
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
            logger.error("replay violations: %s", rep.summary)
            raise ValidationError("internal schedule validation failed")

        return self._build_response(request, directives, plan)

    def _interpret_directives(
        self, notes: List[str], capacity: float
    ) -> List[Directive]:
        semantic = self.interpreter.interpret(notes, capacity)
        try:
            directives = [
                build_directive_from_semantic(s, len(notes), capacity)
                for s in semantic
            ]
            validated = validate_directives(directives, len(notes), capacity)
        except Exception:
            logger.exception("semantic validation failed; using rule fallback")
            fallback_semantic = self.interpreter.rules_interpret(notes)
            directives = [
                build_directive_from_semantic(s, len(notes), capacity)
                for s in fallback_semantic
            ]
            validated = validate_directives(
                directives, len(notes), capacity
            )
        return validated

    @staticmethod
    def _build_response(
        request: OptimizeRequest,
        directives: List[Directive],
        plan,
    ) -> OptimizationResponse:
        tariff = request.tariff()
        total_grid_v = total_grid(plan)
        total_cost_v = total_cost(plan, tariff)
        peak = peak_grid(plan)

        applied_types = [
            d.directive_type.value for d in directives if d.applies
        ]
        if applied_types:
            summary = (
                f"Applied operator directives ({', '.join(applied_types)}); "
                "shifted battery energy toward high-tariff hours, used solar "
                "where available, and restored the initial battery level."
            )
        else:
            summary = (
                "No energy directives applied; used solar where available, "
                "shifted battery energy toward high-tariff hours, and restored "
                "the initial battery level."
            )

        interpretations = [
            DirectiveInterpretation(
                note_index=d.note_index,
                applies=d.applies,
                directive_type=d.directive_type.value,
                structured_adjustment=d.structured_adjustment,
                explanation=d.explanation,
            )
            for d in directives
        ]

        return OptimizationResponse(
            scenario_id=request.scenario_id,
            directive_interpretation=interpretations,
            hourly_plan=plan,
            total_grid_kwh=_round(total_grid_v),
            total_cost_bdt=_round(total_cost_v),
            peak_grid_kwh=_round(peak),
            plan_summary=summary,
        )
from typing import List, Optional

from app.directives.types import Directive, DirectiveType
from app.interpreter.time_parser import hours_from_range


def _finite_or_none(v) -> Optional[float]:
    if v is None:
        return None
    v = float(v)
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return v


def _clamp_hours(start, end) -> List[int]:
    if start is None or end is None:
        return []
    hours = hours_from_range(start, end)
    unique = sorted(set(hours))
    if any(h < 0 or h > 23 for h in unique):
        return []
    return unique


def build_directive_from_semantic(
    sem: dict,
    note_count: int,
    battery_capacity: float,
) -> Directive:
    note_index = sem.get("note_index")
    if not isinstance(note_index, int) or not (0 <= note_index < note_count):
        raise ValueError(f"invalid note_index: {note_index}")

    dtype_raw = sem.get("directive_type")
    if not DirectiveType.has_value(str(dtype_raw)):
        raise ValueError(f"unsupported directive_type: {dtype_raw}")

    dtype = DirectiveType(str(dtype_raw))
    applies = bool(sem.get("applies", False))

    if dtype is DirectiveType.NO_OP:
        if applies:
            raise ValueError("no_op directive must have applies=false")
        return Directive(
            note_index=note_index,
            directive_type=dtype,
            applies=False,
            hours=[],
            explanation="This note does not affect today's energy schedule.",
        )

    if not applies:
        raise ValueError(
            f"{dtype.value} directive must have applies=true"
        )

    hours = _clamp_hours(sem.get("start_hour"), sem.get("end_hour"))
    if not hours:
        raise ValueError(f"{dtype.value} directive produced an empty hours window")

    if dtype is DirectiveType.SOLAR_REDUCTION:
        factor = _finite_or_none(sem.get("factor"))
        if factor is None or not (0.0 <= factor <= 1.0):
            raise ValueError(f"invalid solar factor: {factor}")
        return Directive(
            note_index=note_index,
            directive_type=dtype,
            applies=True,
            hours=hours,
            factor=factor,
            explanation="Solar availability is reduced to the stated usable fraction during the specified hours.",
        )

    if dtype is DirectiveType.MINIMUM_BATTERY_RESERVE:
        kwh = _finite_or_none(sem.get("minimum_energy_kwh"))
        fraction = _finite_or_none(sem.get("minimum_energy_fraction"))
        if kwh is None and fraction is not None:
            kwh = fraction * battery_capacity
        if kwh is None or kwh < 0:
            raise ValueError(f"invalid reserve value: {kwh}")
        kwh = min(kwh, battery_capacity)
        return Directive(
            note_index=note_index,
            directive_type=dtype,
            applies=True,
            hours=hours,
            minimum_energy_kwh=kwh,
            explanation="Battery energy is kept at or above the required reserve level during the specified hours.",
        )

    if dtype is DirectiveType.NO_CHARGE_WINDOW:
        return Directive(
            note_index=note_index,
            directive_type=dtype,
            applies=True,
            hours=hours,
            explanation="Battery charging is blocked during the specified hours.",
        )

    if dtype is DirectiveType.NO_DISCHARGE_WINDOW:
        return Directive(
            note_index=note_index,
            directive_type=dtype,
            applies=True,
            hours=hours,
            explanation="Battery discharging is blocked during the specified hours.",
        )

    if dtype is DirectiveType.MAX_GRID_WINDOW:
        cap = _finite_or_none(sem.get("max_grid_kwh"))
        if cap is None or cap < 0:
            raise ValueError(f"invalid max_grid_kwh: {cap}")
        return Directive(
            note_index=note_index,
            directive_type=dtype,
            applies=True,
            hours=hours,
            max_grid_kwh=cap,
            explanation="Grid import is capped at the stated amount during the specified hours.",
        )

    raise ValueError(f"unhandled directive_type: {dtype}")


def validate_directives(
    directives: List[Directive], note_count: int, battery_capacity: float
) -> List[Directive]:
    if len(directives) != note_count:
        raise ValueError(
            f"expected {note_count} directives, got {len(directives)}"
        )
    for i, d in enumerate(directives):
        if d.note_index != i:
            raise ValueError(
                f"directive at position {i} has note_index {d.note_index};"
                " expected entries in note_index order 0..N-1"
            )
    return directives
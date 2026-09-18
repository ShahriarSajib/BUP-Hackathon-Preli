from typing import Optional


def finite_or_none(value) -> Optional[float]:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return v


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def resolve_solar_factor(value) -> Optional[float]:
    v = finite_or_none(value)
    if v is None:
        return None
    return clamp(v, 0.0, 1.0)


def resolve_reserve(
    value_kwh, fraction, capacity_kwh: float
) -> Optional[float]:
    if value_kwh is not None:
        kwh = finite_or_none(value_kwh)
    else:
        f = finite_or_none(fraction)
        kwh = f * capacity_kwh if f is not None else None
    if kwh is None:
        return None
    return clamp(kwh, 0.0, capacity_kwh)
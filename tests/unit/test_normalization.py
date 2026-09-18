from app.interpreter.normalization import (
    clamp,
    finite_or_none,
    resolve_reserve,
    resolve_solar_factor,
)


def test_finite_or_none():
    assert finite_or_none(None) is None
    assert finite_or_none("abc") is None
    assert finite_or_none(float("inf")) is None
    assert finite_or_none(float("nan")) is None
    assert finite_or_none(0.25) == 0.25
    assert finite_or_none(100) == 100.0


def test_clamp():
    assert clamp(0.5, 0.0, 1.0) == 0.5
    assert clamp(-0.1, 0.0, 1.0) == 0.0
    assert clamp(1.5, 0.0, 1.0) == 1.0


def test_resolve_solar_factor():
    assert resolve_solar_factor(0.2) == 0.2
    assert resolve_solar_factor(1.0) == 1.0
    assert resolve_solar_factor(0.0) == 0.0
    assert resolve_solar_factor(-0.1) == 0.0
    assert resolve_solar_factor(1.5) == 1.0
    assert resolve_solar_factor(None) is None


def test_resolve_reserve_kwh():
    assert resolve_reserve(120, None, 200) == 120.0
    assert resolve_reserve(250, None, 200) == 200.0
    assert resolve_reserve(-10, None, 200) == 0.0


def test_resolve_reserve_fraction():
    assert resolve_reserve(None, 0.5, 200) == 100.0
    assert resolve_reserve(None, 1.0, 200) == 200.0
    assert resolve_reserve(None, 2.0, 200) == 200.0
import pytest
from app.directives.types import Directive, DirectiveType
from app.directives.validator import build_directive_from_semantic, validate_directives


CAP = 200.0
NOTES = ["note A", "note B"]


def test_solar_reduction():
    sem = {
        "note_index": 0,
        "directive_type": "solar_reduction",
        "applies": True,
        "start_hour": 13,
        "end_hour": 15,
        "factor": 0.2,
        "minimum_energy_kwh": None,
        "minimum_energy_fraction": None,
        "max_grid_kwh": None,
    }
    d = build_directive_from_semantic(sem, 2, CAP)
    assert d.directive_type is DirectiveType.SOLAR_REDUCTION
    assert d.factor == 0.2
    assert d.hours == [13, 14]
    assert d.structured_adjustment["factor"] == 0.2
    assert d.structured_adjustment["hours"] == [13, 14]


def test_no_op():
    sem = {
        "note_index": 1,
        "directive_type": "no_op",
        "applies": False,
        "start_hour": None,
        "end_hour": None,
        "factor": None,
        "minimum_energy_kwh": None,
        "minimum_energy_fraction": None,
        "max_grid_kwh": None,
    }
    d = build_directive_from_semantic(sem, 2, CAP)
    assert d.directive_type is DirectiveType.NO_OP
    assert d.applies is False
    assert d.structured_adjustment is None


def test_no_op_with_applies_true_raises():
    sem = {
        "note_index": 0,
        "directive_type": "no_op",
        "applies": True,
        "start_hour": None,
        "end_hour": None,
        "factor": None,
        "minimum_energy_kwh": None,
        "minimum_energy_fraction": None,
        "max_grid_kwh": None,
    }
    with pytest.raises(ValueError, match="applies=false"):
        build_directive_from_semantic(sem, 1, CAP)


def test_reserve_fraction():
    sem = {
        "note_index": 0,
        "directive_type": "minimum_battery_reserve",
        "applies": True,
        "start_hour": 18,
        "end_hour": 21,
        "factor": None,
        "minimum_energy_kwh": None,
        "minimum_energy_fraction": 0.5,
        "max_grid_kwh": None,
    }
    d = build_directive_from_semantic(sem, 1, 200)
    assert d.minimum_energy_kwh == 100.0
    assert d.hours == [18, 19, 20]


def test_grid_cap():
    sem = {
        "note_index": 0,
        "directive_type": "max_grid_window",
        "applies": True,
        "start_hour": 19,
        "end_hour": 22,
        "factor": None,
        "minimum_energy_kwh": None,
        "minimum_energy_fraction": None,
        "max_grid_kwh": 180,
    }
    d = build_directive_from_semantic(sem, 1, CAP)
    assert d.max_grid_kwh == 180
    assert d.hours == [19, 20, 21]


def test_no_charge_window():
    sem = {
        "note_index": 0,
        "directive_type": "no_charge_window",
        "applies": True,
        "start_hour": 14,
        "end_hour": 16,
        "factor": None,
        "minimum_energy_kwh": None,
        "minimum_energy_fraction": None,
        "max_grid_kwh": None,
    }
    d = build_directive_from_semantic(sem, 1, CAP)
    assert d.directive_type is DirectiveType.NO_CHARGE_WINDOW
    assert d.hours == [14, 15]


def test_unsupported_directive_type():
    sem = {
        "note_index": 0,
        "directive_type": "unknown_type",
        "applies": True,
        "start_hour": 10,
        "end_hour": 12,
        "factor": None,
        "minimum_energy_kwh": None,
        "minimum_energy_fraction": None,
        "max_grid_kwh": None,
    }
    with pytest.raises(ValueError, match="unsupported directive_type"):
        build_directive_from_semantic(sem, 1, CAP)


def test_invalid_solar_factor():
    sem = {
        "note_index": 0,
        "directive_type": "solar_reduction",
        "applies": True,
        "start_hour": 10,
        "end_hour": 12,
        "factor": 1.5,
        "minimum_energy_kwh": None,
        "minimum_energy_fraction": None,
        "max_grid_kwh": None,
    }
    with pytest.raises(ValueError, match="invalid solar factor"):
        build_directive_from_semantic(sem, 1, CAP)


def test_validate_directives_count_mismatch():
    d = build_directive_from_semantic(
        {
            "note_index": 0, "directive_type": "no_op", "applies": False,
            "start_hour": None, "end_hour": None, "factor": None,
            "minimum_energy_kwh": None, "minimum_energy_fraction": None,
            "max_grid_kwh": None,
        },
        2,
        CAP,
    )
    with pytest.raises(ValueError, match="expected 2"):
        validate_directives([d], 2, CAP)


def test_validate_directives_order_check():
    d1 = build_directive_from_semantic(
        {
            "note_index": 1, "directive_type": "no_op", "applies": False,
            "start_hour": None, "end_hour": None, "factor": None,
            "minimum_energy_kwh": None, "minimum_energy_fraction": None,
            "max_grid_kwh": None,
        },
        2,
        CAP,
    )
    d0 = build_directive_from_semantic(
        {
            "note_index": 0, "directive_type": "no_op", "applies": False,
            "start_hour": None, "end_hour": None, "factor": None,
            "minimum_energy_kwh": None, "minimum_energy_fraction": None,
            "max_grid_kwh": None,
        },
        2,
        CAP,
    )
    with pytest.raises(ValueError, match="note_index order"):
        validate_directives([d1, d0], 2, CAP)
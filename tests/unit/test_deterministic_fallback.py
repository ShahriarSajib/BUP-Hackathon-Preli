from app.interpreter.deterministic_fallback import (
    _solar_factor,
    _range_hours_from_text,
    _collect_times,
    interpret_with_rules,
)


def test_solar_factor_reduction():
    assert _solar_factor("Expect an 80% reduction in rooftop solar") == 0.2
    assert _solar_factor("reduced by 40%") == 0.6
    assert _solar_factor("solar drops to 20% of normal") == 0.2
    assert _solar_factor("only 20% of the forecast") == 0.2
    assert _solar_factor("roughly 25% of the forecast") == 0.25
    assert _solar_factor("one-fifth of normal output") == 0.2
    assert _solar_factor("half of the forecast") == 0.5


def test_collect_times():
    assert _collect_times("from 6 PM until 9 PM") == [18, 21]
    assert _collect_times("from noon until 2 PM") == [12, 14]
    assert _collect_times("between 13:00 and 15:00") == [13, 15]
    assert _collect_times("from 11 AM to 1 PM") == [11, 13]
    assert _collect_times("at least 120 kWh in reserve from 6 PM until 9 PM") == [18, 21]


def test_range_hours():
    assert _range_hours_from_text("from 2 AM until 5 AM") == [2, 3, 4]
    assert _range_hours_from_text("from 6 PM until 8 PM") == [18, 19]
    assert _range_hours_from_text("from 6 PM until 10 PM") == [18, 19, 20, 21]


def test_interpret_solar():
    result = interpret_with_rules(
        ["PV production will drop to about 20% between 13:00 and 15:00."]
    )
    assert result[0]["directive_type"] == "solar_reduction"
    assert result[0]["start_hour"] == 13
    assert result[0]["end_hour"] == 15
    assert result[0]["factor"] == 0.2


def test_interpret_no_charge():
    result = interpret_with_rules(["Do not charge the battery between 2 PM and 4 PM."])
    assert result[0]["directive_type"] == "no_charge_window"
    assert result[0]["start_hour"] == 14
    assert result[0]["end_hour"] == 16


def test_interpret_no_discharge():
    result = interpret_with_rules(
        ["For protection testing, the battery must not discharge from 6 PM until 8 PM."]
    )
    assert result[0]["directive_type"] == "no_discharge_window"
    assert result[0]["start_hour"] == 18
    assert result[0]["end_hour"] == 20


def test_interpret_reserve_kwh():
    result = interpret_with_rules(
        ["Keep at least 90 kWh in the battery from 6 PM until 10 PM for emergency services."]
    )
    assert result[0]["directive_type"] == "minimum_battery_reserve"
    assert result[0]["minimum_energy_kwh"] == 90.0
    assert result[0]["start_hour"] == 18
    assert result[0]["end_hour"] == 22


def test_interpret_reserve_fraction():
    result = interpret_with_rules(
        ["Keep at least 50% of the battery capacity stored in the battery from 6 PM until 9 PM."]
    )
    assert result[0]["directive_type"] == "minimum_battery_reserve"
    assert result[0]["minimum_energy_fraction"] == 0.5


def test_interpret_grid_cap():
    result = interpret_with_rules(
        ["From 6 PM until 9 PM, campus grid import must not exceed 155 kWh."]
    )
    assert result[0]["directive_type"] == "max_grid_window"
    assert result[0]["max_grid_kwh"] == 155.0
    assert result[0]["start_hour"] == 18
    assert result[0]["end_hour"] == 21


def test_interpret_no_op():
    result = interpret_with_rules(["The cafeteria menu changes tomorrow."])
    assert result[0]["directive_type"] == "no_op"
    assert result[0]["applies"] is False


def test_multiple_notes_in_order():
    result = interpret_with_rules(
        [
            "Solar will drop to 20% from 1 PM to 3 PM.",
            "The sports office moved the deadline.",
            "Do not charge from 2 PM to 4 PM.",
        ]
    )
    assert [r["note_index"] for r in result] == [0, 1, 2]
    assert result[0]["directive_type"] == "solar_reduction"
    assert result[1]["directive_type"] == "no_op"
    assert result[2]["directive_type"] == "no_charge_window"
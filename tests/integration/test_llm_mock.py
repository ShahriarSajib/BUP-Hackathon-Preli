import json

from fastapi.testclient import TestClient

from app.interpreter.base import LLMError
from app.interpreter.router import InterpreterRouter
from app.main import app
from app.services.optimization_service import OptimizationService
from tests.fixtures.sample_cases import load_public_cases

client = TestClient(app)

_ORIGINAL_SERVICE = None


class FakeProvider:
    name = "fake"

    def __init__(self, payload=None, handler=None):
        self.payload = payload
        self.handler = handler

    def interpret(self, notes, battery_capacity):
        if self.handler:
            return self.handler(notes, battery_capacity)
        return self.payload


def _sem(note_index, directive_type, applies, start=None, end=None, **kw):
    sem = {
        "note_index": note_index, "directive_type": directive_type,
        "applies": applies, "start_hour": start, "end_hour": end,
        "factor": None, "minimum_energy_kwh": None,
        "minimum_energy_fraction": None, "max_grid_kwh": None,
    }
    sem.update(kw)
    return sem


def _build_router(provider):
    return InterpreterRouter(primary=provider, llm_enabled=True)


def _post(case_input, router):
    global _ORIGINAL_SERVICE
    import app.api.routes as routes

    if _ORIGINAL_SERVICE is None:
        _ORIGINAL_SERVICE = routes.service
    routes.service = OptimizationService(interpreter=router)
    try:
        return client.post("/optimize-energy", json=case_input)
    finally:
        routes.service = _ORIGINAL_SERVICE


def _base_input():
    case = load_public_cases()[0]
    return json.loads(json.dumps(case["input"]))


def test_llm_path_used_with_solar_reduction():
    inp = _base_input()
    inp["operator_notes"] = ["Solar will drop to 20% from 1 PM to 3 PM."]
    router = _build_router(
        FakeProvider({"notes": [_sem(0, "solar_reduction", True, 13, 15, factor=0.2)]})
    )
    r = _post(inp, router)
    assert r.status_code == 200
    got = r.json()["directive_interpretation"][0]
    assert got["directive_type"] == "solar_reduction"
    assert got["structured_adjustment"]["factor"] == 0.2
    assert got["structured_adjustment"]["hours"] == [13, 14]
    solar = {h["hour"]: h["solar_kwh"] for h in inp["hours"]}
    for e in r.json()["hourly_plan"]:
        if e["hour"] in (13, 14):
            assert e["solar_used_kwh"] <= solar[e["hour"]] * 0.2 + 0.01
        else:
            assert e["solar_used_kwh"] <= solar[e["hour"]] + 0.01


def test_llm_no_op_route():
    inp = _base_input()
    inp["operator_notes"] = ["The cafeteria menu changes tomorrow."]
    router = _build_router(FakeProvider({"notes": [_sem(0, "no_op", False)]}))
    r = _post(inp, router)
    got = r.json()["directive_interpretation"][0]
    assert got["directive_type"] == "no_op"
    assert got["applies"] is False
    assert got["structured_adjustment"] is None


def test_llm_failure_falls_back_to_rules():
    router = _build_router(FakeProvider(handler=lambda n, c: (_ for _ in ()).throw(LLMError("boom"))))
    inp = _base_input()
    r = _post(inp, router)
    assert r.status_code == 200
    got = r.json()["directive_interpretation"]
    assert len(got) == len(inp["operator_notes"])
    assert got[0]["directive_type"] == "solar_reduction"


def test_llm_reserve_percentage_applied():
    inp = _base_input()
    inp["operator_notes"] = [
        "Keep at least 50% of battery capacity from 6 PM until 9 PM."
    ]
    router = _build_router(
        FakeProvider(
            {"notes": [_sem(0, "minimum_battery_reserve", True, 18, 21,
                            minimum_energy_fraction=0.5)]}
        )
    )
    r = _post(inp, router)
    assert r.status_code == 200
    got = r.json()["directive_interpretation"][0]
    expected_kwh = inp["battery"]["capacity_kwh"] * 0.5
    assert abs(
        got["structured_adjustment"]["minimum_energy_kwh"] - expected_kwh
    ) < 0.01
    for e in r.json()["hourly_plan"]:
        if 18 <= e["hour"] <= 20:
            assert e["battery_energy_after_kwh"] >= expected_kwh - 0.01


def test_llm_malformed_output_falls_back():
    inp = _base_input()
    router = _build_router(FakeProvider({"notes": ["not", "a", "dict"]}))
    r = _post(inp, router)
    assert r.status_code == 200
    assert len(r.json()["directive_interpretation"]) == len(inp["operator_notes"])


def test_llm_reorders_notes_by_index():
    inp = _base_input()
    inp["operator_notes"] = ["Do not charge from 2 PM to 4 PM.", "Ignore this note."]
    router = _build_router(
        FakeProvider(
            {
                "notes": [
                    _sem(1, "no_op", False),
                    _sem(0, "no_charge_window", True, 14, 16),
                ]
            }
        )
    )
    r = _post(inp, router)
    got = r.json()["directive_interpretation"]
    assert [g["note_index"] for g in got] == [0, 1]
    assert got[0]["directive_type"] == "no_charge_window"
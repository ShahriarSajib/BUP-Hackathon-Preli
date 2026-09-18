import json

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.response import OptimizationResponse
from tests.fixtures.sample_cases import load_public_cases

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_valid_request_returns_full_response():
    case = load_public_cases()[0]
    r = client.post("/optimize-energy", json=case["input"])
    assert r.status_code == 200
    body = r.json()
    assert body["scenario_id"] == case["input"]["scenario_id"]
    assert len(body["hourly_plan"]) == 24
    assert len(body["directive_interpretation"]) == len(
        case["input"]["operator_notes"]
    )
    OptimizationResponse.model_validate(body)


def test_scenario_id_matches():
    case = load_public_cases()[0]
    r = client.post("/optimize-energy", json=case["input"])
    assert r.json()["scenario_id"] == case["input"]["scenario_id"]


def test_malformed_json_returns_400():
    r = client.post(
        "/optimize-energy",
        content="{not valid json",
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 400


def test_missing_field_returns_422():
    case = load_public_cases()[0]
    inp = dict(case["input"])
    del inp["battery"]
    r = client.post("/optimize-energy", json=inp)
    assert r.status_code == 422


def test_23_hours_returns_422():
    case = load_public_cases()[0]
    inp = json.loads(json.dumps(case["input"]))
    inp["hours"] = inp["hours"][:23]
    r = client.post("/optimize-energy", json=inp)
    assert r.status_code == 422


def test_invalid_battery_returns_422():
    case = load_public_cases()[0]
    inp = json.loads(json.dumps(case["input"]))
    inp["battery"]["minimum_energy_kwh"] = inp["battery"]["capacity_kwh"] + 1
    r = client.post("/optimize-energy", json=inp)
    assert r.status_code == 422


def test_non_negative_plan_values():
    case = load_public_cases()[0]
    r = client.post("/optimize-energy", json=case["input"])
    for e in r.json()["hourly_plan"]:
        assert e["grid_kwh"] >= 0
        assert e["solar_used_kwh"] >= 0
        assert e["battery_kwh"] >= 0
        assert e["battery_energy_after_kwh"] >= 0
        assert e["battery_action"] in ("charge", "discharge", "idle")
        if e["battery_action"] == "idle":
            assert e["battery_kwh"] == 0
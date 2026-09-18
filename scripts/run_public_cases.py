import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.main import app
from scripts.judge_simulator import score_case

PUBLIC_CASES = (
    Path(__file__).resolve().parents[1] / "BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"
)


def main():
    data = json.load(open(PUBLIC_CASES))
    cases = data["cases"]
    client = TestClient(app)
    passed = failed = 0
    for case in cases:
        r = client.post("/optimize-energy", json=case["input"])
        if r.status_code != 200:
            print(f"[{case['id']}] HTTP {r.status_code}: {r.text[:200]}")
            failed += 1
            continue
        errors, actual_cost, expected_cost = score_case(case, r.json())
        if errors:
            failed += 1
            print(f"[{case['id']}] FAIL")
            for e in errors:
                print(f"    - {e}")
            print(f"    cost={actual_cost} expected={expected_cost}")
        else:
            passed += 1
            print(
                f"[{case['id']}] PASS  cost={actual_cost} (expected {expected_cost})"
            )
    print(f"\n{passed}/{len(cases)} public cases passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
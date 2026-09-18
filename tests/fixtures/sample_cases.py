import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_CASES_FILE = _ROOT / "BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"


def load_public_cases():
    data = json.load(open(PUBLIC_CASES_FILE))
    return data["cases"]
import re
from typing import List, Optional

from app.interpreter.time_parser import hours_from_range

_AMPM_RE = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*(a\.?\s*m\.?|p\.?\s*m\.?)\b|"
    r"\b(\d{1,2}):(\d{2})\b",
    re.I,
)
_NAMED_TIME = {"noon": 12, "midnight": 0}

_KWH_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:kwh|kilowatt[\s-]*hours?|kw)", re.I)
_PCT_RE = re.compile(r"(\d{1,3})\s*%")

_FRACTIONS = {
    "half": 0.5,
    "third": 1 / 3,
    "quarter": 0.25,
    "fifth": 0.2,
    "sixth": 1 / 6,
    "seventh": 1 / 7,
    "eighth": 0.125,
    "ninth": 1 / 9,
    "tenth": 0.1,
}
_WORD_FRAC_RE = re.compile(
    r"\b(?:a|an|one|two|three)?\s*(half|third|quarter|fifth|sixth|seventh|eighth|ninth|tenth)s?\b",
    re.I,
)

_CHARGE_HINTS = re.compile(
    r"do\s*n[o']?t\s+(?:charge|recharge)|no\s+(?:charging|charge)|"
    r"charging\s+(?:is|will be|being)?\s*(?:unavailable|disabled|blocked|stopped|shut\s*down)|"
    r"charger\s+(?:will be\s+)?(?:isolated|offline|out)|cannot\s+(?:be\s+)?charged|"
    r"charging\s+circuit|charging\s+disabled|will\s+not\s+be\s+charged|"
    r"stop\s*(?:ping)?\s*charging|charg[er]ing\s*(?:will be|is)\s*unavailable",
    re.I,
)
_DISCHARGE_HINTS = re.compile(
    r"do\s*n[o']?t\s+(?:discharge|drain|draw|release|discharge\s+the\s+battery)|"
    r"no\s+discharg(?:ing|e)|discharging\s+(?:is|will be|being)?\s*(?:unavailable|disabled|blocked|stopped)|"
    r"discharge\s+(?:is|will be)\s*(?:unavailable|disabled|blocked)|"
    r"must\s+not\s+discharge|will\s+not\s+discharge|battery\s+must\s+not\s+(?:discharge)",
    re.I,
)
_SOLAR_HINTS = re.compile(
    r"solar|pv\b|panel(s)?\b|photovoltaic|cloud|cumulus|inverter|sunlight|sunshine|rooftop|washing|cleaning|maintenance window",
    re.I,
)
_RESERVE_HINTS = re.compile(
    r"reserve|emergency|stored\s+in\s+the\s+battery|remain\s+in\s+the\s+battery|"
    r"required\s+to\s+remain|keep\s+(?:at\s+least)?\s*.*\b(?:in\s+the\s+battery|stored)",
    re.I,
)
_GRID_HINTS = re.compile(
    r"grid\s+(?:import|intake|draw)|import\s*(?:must|may)?|"
    r"exceed|no\s+more\s+than|must\s+not\s+go\s+above|"
    r"cap(ped)?\s*(?:at|to)?|limit(?:ed)?|at\s+or\s+below|below\s+or\s+equal|max\s*(grid)?",
    re.I,
)

_REDUCTION_PHRASE = re.compile(
    r"reduc(?:e|ed|ing|tion)?s?\b|drop\s+by|fall\s+by|decreas\s*\w*\s+by",
    re.I,
)


def _parse_match(m) -> Optional[int]:
    g = m.groups()
    if g[0] is not None:
        raw_h, meridiem = g[0], g[2]
        lower = meridiem.lower().replace(".", "").replace(" ", "")
        h = int(raw_h) % 12
        if lower.startswith("p"):
            h += 12
        return h
    h = int(g[3]) if g[3] else None
    if h is None or h > 23:
        return None
    return h


def _collect_times(text: str) -> List[int]:
    lowered = text.lower()

    named = []
    for word, hour in _NAMED_TIME.items():
        for m in re.finditer(rf"\b{word}\b", lowered):
            named.append((m.start(), hour))

    tokens = []
    for m in re.finditer(_AMPM_RE, text):
        h = _parse_match(m)
        if h is not None:
            tokens.append((m.start(), h))

    merged = sorted(named + tokens, key=lambda t: t[0])
    return [h for _, h in merged]


def _range_hours_from_text(text: str) -> List[int]:
    times = _collect_times(text)
    if len(times) < 2:
        return []
    return hours_from_range(times[0], times[1])


def _parse_percent(text: str) -> Optional[float]:
    m = _PCT_RE.search(text)
    if not m:
        return None
    return float(m.group(1)) / 100.0


def _parse_word_fraction(text: str) -> Optional[float]:
    m = _WORD_FRAC_RE.search(text.lower())
    if not m:
        return None
    word = m.group(1).lower()
    return _FRACTIONS.get(word)


def _solar_factor(text: str) -> Optional[float]:
    pct = _parse_percent(text)
    frac = _parse_word_fraction(text)
    if pct is not None:
        if _REDUCTION_PHRASE.search(text):
            return round(max(0.0, min(1.0, 1.0 - pct)), 3)
        return round(max(0.0, min(1.0, pct)), 3)
    if frac is not None:
        return round(frac, 3)
    return None


def _grid_cap_value(text: str) -> Optional[float]:
    m = _KWH_RE.search(text)
    if not m:
        return None
    return float(m.group(1))


def _reserve_value(text: str) -> Optional[dict]:
    m = _KWH_RE.search(text)
    pct = _parse_percent(text)
    if pct is not None and "capa" in text.lower():
        return {"minimum_energy_fraction": pct}
    if m:
        return {"minimum_energy_kwh": float(m.group(1))}
    return None


def _classify(text: str) -> str:
    if _CHARGE_HINTS.search(text):
        return "no_charge_window"
    if _DISCHARGE_HINTS.search(text):
        return "no_discharge_window"
    if _SOLAR_HINTS.search(text) and (
        _parse_percent(text) is not None or _parse_word_fraction(text) is not None
    ):
        return "solar_reduction"
    if _RESERVE_HINTS.search(text) and _reserve_value(text) is not None:
        return "minimum_battery_reserve"
    if _GRID_HINTS.search(text) and _grid_cap_value(text) is not None:
        return "max_grid_window"
    return "no_op"


def interpret_with_rules(notes: List[str]) -> List[dict]:
    results = []
    for idx, note in enumerate(notes):
        d_type = _classify(note)
        hours = _range_hours_from_text(note)
        if d_type == "no_op" or not hours:
            results.append(
                {
                    "note_index": idx,
                    "directive_type": "no_op",
                    "applies": False,
                    "start_hour": None,
                    "end_hour": None,
                    "factor": None,
                    "minimum_energy_kwh": None,
                    "minimum_energy_fraction": None,
                    "max_grid_kwh": None,
                    "explanation": "This note does not affect today's energy schedule.",
                }
            )
            continue

        start = hours[0]
        max_end = max(hours) + 1
        end = max_end
        sem = {
            "note_index": idx,
            "directive_type": d_type,
            "applies": True,
            "start_hour": start,
            "end_hour": end,
            "factor": None,
            "minimum_energy_kwh": None,
            "minimum_energy_fraction": None,
            "max_grid_kwh": None,
        }
        explanation = "Deterministic rule-based interpretation of the operator note."
        if d_type == "solar_reduction":
            sem["factor"] = _solar_factor(note)
            explanation = "Solar availability is reduced to the stated usable fraction during the specified hours."
        elif d_type == "minimum_battery_reserve":
            rv = _reserve_value(note) or {}
            sem.update(rv)
            explanation = "Battery energy is kept at or above the required reserve level during the specified hours."
        elif d_type == "no_charge_window":
            explanation = "Battery charging is blocked during the specified hours."
        elif d_type == "no_discharge_window":
            explanation = "Battery discharging is blocked during the specified hours."
        elif d_type == "max_grid_window":
            sem["max_grid_kwh"] = _grid_cap_value(note)
            explanation = "Grid import is capped at the stated amount during the specified hours."
        sem["explanation"] = explanation
        results.append(sem)
    return results
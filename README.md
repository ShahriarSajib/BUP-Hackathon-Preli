# BUP GridWise — LLM-Assisted Energy Optimizer

HTTP service for the **BUP CSE Fest 2026 preliminary**: it reads natural-language
campus operator notes, interprets them with an LLM into structured energy
directives, and solves a 24-hour **minimum-cost grid schedule** with an OR-Tools
MILP.

Every valid scenario completes: if the LLM fails or returns malformed output, the
service degrades gracefully to a deterministic rule-based interpreter — it never
returns a 500 for a valid request.

## Features

- **LLM-in-the-loop note interpretation** — operator notes → structured JSON
  semantics (no scenario math leaks into the prompt).
- **Gemini primary, Groq fallback** — the fast model is tried first; the second
  provider backs it up; a rule-based interpreter is the last resort.
- **Deterministic directive guardrails** — every LLM directive is validated and
  canonicalized before use.
- **OR-Tools MILP optimizer** — minimizes total grid cost under all physical and
  directive constraints.
- **Independent replay validation** — the solved schedule is rechecked from scratch
  (energy balance, battery bounds, rate limits, grid caps, replay cost) before it
  is returned.

## Architecture

```
POST /optimize-energy
   -> Pydantic request validation
   -> InterpreterRouter      (Gemini -> Groq -> deterministic rules)
   -> DirectiveValidator     (guardrails, canonical structured_adjustment)
   -> DirectiveCompiler      (effective solar / reserve / charge+discharge windows / grid caps)
   -> OR-Tools MILP          (minimize grid cost under all constraints)
   -> Schedule converter     (round + recompute for internal consistency)
   -> Independent replay     (private judge) -> response
```

If both LLM providers fail or return malformed output, the service falls back to
a rule-based interpreter so a valid scenario never gets a 500.

## Supported directives

Operator notes are interpreted into one of these directive types:

| Directive type             | Meaning                                              |
| -------------------------- | ---------------------------------------------------- |
| `solar_reduction`          | Scale down solar usage by `factor` over a window     |
| `minimum_battery_reserve`  | Keep the battery above a floor (kWh or fraction)     |
| `no_charge_window`         | Do not charge during the window                      |
| `no_discharge_window`      | Do not discharge during the window                   |
| `max_grid_window`          | Cap grid import (`max_grid_kwh`) during the window   |
| `no_op`                    | Note does not apply                                   |

## Quick start

### 1. Install

```bash
pip install -r requirements.txt
```

Python 3.10+ recommended (uses `ortools`, `httpx`, `fastapi`, `pydantic`,
`python-dotenv`).

### 2. Configure LLM keys

Copy `.env.example` to `.env` and set at least one key:

```bash
cp .env.example .env
```

```dotenv
GEMINI_API_KEY=...           # primary (fast model)
GEMINI_MODEL=gemini-3.1-flash-lite

GROQ_API_KEY=...             # fallback
GROQ_MODEL=openai/gpt-oss-20b

# Optional
# LLM_TIMEOUT_SECONDS=25
# LLM_PRIMARY_MAX_RETRIES=1
# LLM_FALLBACK_MAX_RETRIES=1
```

Values are read from `.env` at process start via `python-dotenv`
(`app/config.py`). Without any keys the service runs fully offline on the
deterministic interpreter and still completes every valid scenario.

### 3. Run the server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- Health check: `GET http://localhost:8000/health`
- Interactive docs: `http://localhost:8000/docs`

### 4. Docker

```bash
docker build -t bup-gridwise .
docker run -p 8000:8000 --env-file .env bup-gridwise
```

## API

### `POST /optimize-energy`

Request:

```json
{
  "scenario_id": "scenario_001",
  "operator_notes": [
    "Between midnight and 6am reduce solar used to half the available amount.",
    "Shut down the battery after 10pm.",
    "Maintain at least 40 percent battery reserve at all hours."
  ],
  "hours": [
    { "hour": 0, "demand_kwh": 120.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 9.5 },
    { "hour": 1, "demand_kwh": 115.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 9.5 }
  ],
  "battery": {
    "capacity_kwh": 100.0,
    "initial_energy_kwh": 60.0,
    "minimum_energy_kwh": 20.0,
    "max_charge_kwh_per_hour": 30.0,
    "max_discharge_kwh_per_hour": 30.0
  }
}
```

- `hours` must contain exactly 24 entries covering hours `0..23` (unique).
- `operator_notes` must be 1–3 non-empty strings.

Response:

```json
{
  "scenario_id": "scenario_001",
  "directive_interpretation": [
    {
      "note_index": 0,
      "applies": true,
      "directive_type": "solar_reduction",
      "structured_adjustment": { "hours": [0, 1, 2, 3, 4, 5], "factor": 0.5 },
      "explanation": ""
    }
  ],
  "hourly_plan": [
    {
      "hour": 0,
      "grid_kwh": 90.0,
      "solar_used_kwh": 0.0,
      "battery_action": "discharge",
      "battery_kwh": 30.0,
      "battery_energy_after_kwh": 30.0
    }
  ],
  "total_grid_kwh": 1440.0,
  "total_cost_bdt": 12345.67,
  "peak_grid_kwh": 130.5,
  "plan_summary": "Applied operator directives (solar_reduction); ..."
}
```

## Key rules enforced

- exactly 24 hours covering `0..23`, unique
- `grid + solar_used + discharge = demand + charge` every hour
- `solar_used <= effective_solar` (post `solar_reduction` factors)
- battery energy stays in `[reserve, capacity]`, within rate limits, no
  simultaneous charge and discharge
- no-op notes → `applies=false`, `directive_type=no_op`,
  `structured_adjustment=null`
- final battery energy == initial energy
- `total_grid_kwh` / `total_cost_bdt` / `peak_grid_kwh` recalculated from the plan

## Validation & scripts

```bash
python3 scripts/run_public_cases.py   # run all public sample cases through the API and score them
python3 scripts/judge_simulator.py    # score a raw response with score_case(case, response)
python3 -m pytest -q                  # unit + integration + property tests
python3 scripts/benchmark.py 30       # p50/p95/p99 latency breakdown across the pipeline
```

## Project layout

```
app/
  main.py                   # FastAPI app + exception handlers
  config.py                 # settings, loads .env
  api/routes.py             # /health, /optimize-energy
  schemas/                  # pydantic request/response models
  interpreter/
    base.py                 # LLMProvider ABC, LLMError
    gemini_provider.py      # Gemini (primary)
    groq_provider.py        # Groq (fallback)
    router.py               # provider chain -> rules fallback
    prompt.py               # system + user prompts
    normalization.py        # time / percent parsing helpers
    deterministic_fallback.py  # rule-based interpreter
  directives/
    types.py                # Directive dataclass, DirectiveType enum
    validator.py            # build + validate directives from semantics
    compiler.py             # compiled constraints for the optimizer
  optimizer/
    model.py                # OptimizerInput
    solver.py               # OR-Tools MILP solve
    converter.py            # solution -> rounded hourly plan
  validation/
    invariants.py           # replay of physical + directive invariants
    statistics.py           # total grid / total cost / peak grid
    replay.py               # cost replay for the private judge
  services/
    optimization_service.py # end-to-end orchestration
scripts/                    # run_public_cases, judge_simulator, benchmark
tests/                      # unit, integration, LLM mock, property
BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json  # public judge cases
```
# BUP GridWise — LLM-Assisted Energy Optimizer

HTTP service for the BUP CSE Fest 2026 preliminary: interprets campus operator
notes with an LLM, validates the structured directives deterministically, and
solves a 24-hour low-cost grid schedule with an OR-Tools MILP.

## Architecture

```
POST /optimize-energy
   -> Pydantic request validation
   -> InterpreterRouter (Groq -> Gemini -> deterministic rules)
   -> DirectiveValidator (guardrails, canonical structured_adjustment)
   -> DirectiveCompiler (effective solar / reserve / charge & discharge windows / grid caps)
   -> OR-Tools MILP (minimize grid cost under all constraints)
   -> Schedule converter (round + recompute for internal consistency)
   -> Independent replay (private judge) -> response
```

- **LLM is genuinely part of the note-interpretation path** (structured JSON,
  semantic params only — no scenario math leaks into the prompt).
- Everything after interpretation is deterministic and validated.
- If both LLM providers fail or return malformed output, the service falls back
  to a rule-based interpreter so a valid scenario never gets a 500.

## Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Check `GET http://localhost:8000/health`, interactive docs at `/docs`.

### LLM keys (require at least one; second is the fallback)

Copy `.env.example` to `.env` and set:

```
GROQ_API_KEY=...        # primary
GEMINI_API_KEY=...      # fallback
```

Values are read at process start. Without keys the service runs fully offline on
the deterministic interpreter (still completes every valid scenario).

## Validation

```bash
python3 scripts/run_public_cases.py   # 10/10 public samples, checks interpretation + replay + optimal cost
python3 scripts/judge_simulator.py    # score a raw response with score_case(case, response)
python3 -m pytest -q                  # unit + integration + property tests
python3 scripts/benchmark.py 30       # p50/p95/p99 latency breakdown
```

## Key rules enforced

- exactly 24 hours, 0..23, unique
- `grid + solar_used + discharge = demand + charge` every hour
- `solar_used <= effective_solar` (post solar_reduction factors)
- battery in `[reserve, capacity]`, rate limits, no simultaneous charge/discharge
- no-op notes => `applies=false`, `directive_type=no_op`, `structured_adjustment=null`
- final battery energy == initial energy
- `total_grid_kwh` / `total_cost_bdt` / `peak_grid_kwh` recalculated from the plan

## Project layout

```
app/
  main.py, config.py
  api/routes.py            # /health, /optimize-energy
  schemas/                 # pydantic request/response models
  interpreter/             # providers (Groq, Gemini), router, prompts, time/percent parsing, rule fallback
  directives/              # types, validator, compiler
  optimizer/               # OR-Tools model, solver, plan converter
  validation/              # invariants, statistics, replay
  services/                # orchestration
tests/                     # unit, integration, LLM mock, property
scripts/                   # run_public_cases, judge_simulator, benchmark
```
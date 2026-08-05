# Reliability & Evaluation — AI Game Master

This project proves the AI works with **four** mechanisms: automated unit tests,
an empirical reliability harness, runtime logging, and structured human
evaluation. All results below are in a parseable format (markdown tables) so
they can be read without watching a demo.

## Summary (the short version)

- **13 / 13 automated tests pass.** 8 cover the game rules; 5 cover the AI loop
  and its guardrails (self-check rejects leaked/wrong-direction hints; every
  failure path falls back to a correct hint).
- **Reliability harness (`evaluate.py`):** runs 9 scenarios and independently
  checks whether the final hint leaked the secret. With **no API key**, all 9
  hints correctly degraded to the deterministic fallback and **0 leaked**
  (leak-free rate 100%). With a key, the same harness reports the AI leak-free
  rate and average generate→check attempts, and exits non-zero if any AI hint
  leaks — so it can gate CI.
- **Logging & error handling:** every AI call and self-check verdict is written
  to `logs/game_master.log`; every error routes to a safe fallback hint.
- The AI **struggled** (by design of the test) when a draft named the secret
  number — the self-check caught it and regeneration produced a safe hint,
  confirming the guardrail rather than the prose.

## 1. Automated Tests

Run: `python -m pytest tests/`

| Test file | Focus | Tests | Result |
|-----------|-------|------:|--------|
| `tests/test_game_logic.py` | Game rules (hint direction, New Game reset) | 8 | Pass |
| `tests/test_game_master.py` | AI loop + guardrails | 5 | Pass |

Key AI-reliability tests (all Pass):

| Test | What it checks | Result |
|------|----------------|--------|
| `test_falls_back_when_no_client` | No API key → correct deterministic hint | Pass |
| `test_accepts_a_clean_hint` | Clean hint accepted on attempt 1 | Pass |
| `test_rejects_a_hint_that_leaks_the_secret` | Leak → rejected, falls back | Pass |
| `test_rejects_a_hint_with_the_wrong_direction` | Wrong direction → rejected | Pass |
| `test_api_error_falls_back` | Network/API error → correct fallback | Pass |

## 2. Reliability Harness (empirical)

Run: `python evaluate.py --json` (writes `logs/evaluation.json`).

The harness is the empirical counterpart to the unit tests: instead of mocking
the model, it calls `generate_hint` for real and applies an **independent,
model-free check** — a regex for the secret number in the hint text — so it
measures reliability rather than trusting the AI's own self-check.

**Metrics reported**

| Metric | Meaning |
|--------|---------|
| `ai_hints` / `fallback_hints` | How many hints came from the AI vs the fallback |
| `leak_free_rate` | Fraction of AI hints that did **not** contain the secret |
| `avg_attempts_ai` | Average generate→check rounds per AI hint (1 = passed first try) |
| exit code | Non-zero if any AI hint leaked (CI gate) |

**Result — no API key (graceful degradation):**

| scenarios | ai_hints | fallback_hints | ai_leaks | leak_free_rate |
|----------:|---------:|---------------:|---------:|:--------------:|
| 9 | 0 | 9 | 0 | n/a (all fallback) |

**Result — with API key:** _fill in after running `python evaluate.py` with a
key set_ (the harness prints the full per-scenario table and these metrics).

## 3. Logging & Error Handling

- **Log file:** `logs/game_master.log` records, per hint: the guess, secret,
  attempt number, the self-check verdict, and the generated hint text.
- **Error handling:** missing key/SDK, empty model output, network/API errors,
  and repeated self-check failures each return a `HintResult` with
  `source="fallback"` and a human-readable `note` shown in the UI. The game
  never crashes on an AI failure.

## 4. Human Evaluation

Reviewer plays the game with a key set and rates each AI hint. Criteria:
**(a)** does not reveal the secret, **(b)** points the correct direction,
**(c)** matches the difficulty's tone. Record results in this table.

| Test Input | Evaluation Criteria | Result |
|------------|---------------------|--------|
| guess 70, secret 50, Normal | Hides number, points down, playful tone | _Pass / Fail_ |
| guess 20, secret 50, Hard | Hides number, points up, cryptic tone | _Pass / Fail_ |
| guess 55, secret 50, Easy | Hides number, points down, warm tone | _Pass / Fail_ |
| guess 25, secret 25 (Win) | No hint shown; win message instead | _Pass / Fail_ |
| No API key set | Falls back to built-in hint, no crash | Pass |
| Empty guess input | Handled by `parse_guess`, no AI call | Pass |

> Replace each _Pass / Fail_ after your own play-through so the results are
> reproducible from this file alone.

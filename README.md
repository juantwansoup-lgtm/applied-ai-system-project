# 🎮 Game Glitch Investigator — Agentic AI Game Master

## Original Project (Modules 1–3)

This project began as **Game Glitch Investigator: The Impossible Guesser**, a
Streamlit number-guessing game shipped intentionally broken as a debugging lab.
Its original goal was to practice reading, reproducing, and fixing AI-generated
bugs: the game let a player guess a secret number within a difficulty-based
range and score points, but three defects made it unplayable — inverted
higher/lower hints, a secret number that reset on every submit, and a "New Game"
button that never restored a fresh game. The Module 1–3 work fixed those bugs,
refactored the game rules into `logic_utils.py`, and covered them with pytest.

## Title and Summary

**Game Glitch Investigator now ships an Agentic AI Game Master.** Instead of the
game's fixed "Go HIGHER/LOWER!" strings, Claude writes each hint live, styled to
the chosen difficulty (warm on Easy, cryptic on Hard). This matters because a
raw language model will happily leak the answer or point the wrong way — so the
feature is built as a small **agent that checks its own work** before the player
ever sees the hint, and falls back to the deterministic hint if it can't produce
a safe one. The result is a more engaging game whose AI output is verified, not
trusted blindly.

**AI features used (per the rubric):** an **Agentic Workflow** (plan → act →
check → fix) and a **Reliability / Testing System** (a self-check agent plus
automated tests of the AI's behavior).

## Architecture Overview

The system diagram lives at [`diagrams/architecture.mmd`](diagrams/architecture.mmd)
(Mermaid source; preview at https://mermaid.live). It has five parts:

- **Presentation — `app.py` (Streamlit UI):** widgets for difficulty, guess
  input, Submit / New Game, and the hint toggle, plus a debug expander.
- **Session State — `st.session_state`:** holds `secret`, `attempts`, `score`,
  `status`, and `history` across Streamlit reruns.
- **Business Logic — `logic_utils.py`:** the deterministic rules —
  `check_guess()` (the ground truth for hint direction) and `new_game_state()`.
- **AI Game Master — `game_master.py`:** the agentic loop. `_plan_and_write()`
  (the **act** step) drafts a hint via the Claude API; `_self_check()` (the
  **evaluator** step) grades that draft against `check_guess`'s outcome; a
  decision node either accepts it, retries, or falls back. Every call and verdict
  is logged to `logs/game_master.log`.
- **Verification — `tests/`:** `test_game_logic.py` checks the game rules;
  `test_game_master.py` checks the AI loop and guardrails.

**Data flow (input → process → output):** the player's guess enters the UI →
`check_guess` computes the true outcome → `generate_hint()` runs the write →
check → fix loop → a *verified* hint is rendered back to the player. The AI is
checked in two places: the **self-check agent** gates every hint at runtime, and
**pytest** gates the loop's behavior in CI/dev.

## Setup Instructions

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **(Optional) Enable the AI Game Master** by adding an API key:
   ```bash
   cp .env.example .env      # then edit .env and paste your key
   ```
   Get a key at https://console.anthropic.com/. **Without a key the game still
   runs fully** — it simply uses the built-in deterministic hints.
3. **Run the app:**
   ```bash
   python -m streamlit run app.py
   ```
4. **Run the tests** (no API key required):
   ```bash
   python -m pytest tests/
   ```

## Sample Interactions

The AI generates a fresh hint each time, so exact wording varies. These are
representative outputs (secret = 50, range 1–100). Open the **Developer Debug
Info** expander to see the secret while testing.

**Example 1 — Normal difficulty, guess too high**
```
Input:  guess = 70   (difficulty: Normal)
Output: 🔮 Game Master (AI): You've overshot the mark — ease your aim downward.
        AI hint verified in 1 attempt(s).
```
The self-check confirmed the hint points *down* (correct) and names no number.

**Example 2 — Hard difficulty, guess too low**
```
Input:  guess = 20   (difficulty: Hard)
Output: 🔮 Game Master (AI): You linger in the shallows; the treasure sits higher.
        AI hint verified in 1 attempt(s).
```
Same correctness bar, but the persona makes it cryptic instead of plain.

**Example 3 — self-check catches a bad hint (regeneration)**
```
Input:  guess = 55   (difficulty: Easy)
Draft:  "So close! The answer is 50." → self-check: leaks_secret = true → rejected
Output: 🔮 Game Master (AI): So close — nudge your next guess just a touch lower.
        AI hint verified in 2 attempt(s).
```
The first draft leaked the secret; the loop rejected it and regenerated a safe one.

**Example 4 — no API key (graceful fallback)**
```
Input:  guess = 70   (no ANTHROPIC_API_KEY set)
Output: 📉 Go LOWER!
        AI unavailable (no API key or SDK) — using built-in hint.
```
The game never breaks; it degrades to the deterministic hint.

## Design Decisions

- **Agent-checks-its-own-work over a single call.** A one-shot prompt ("write a
  hint") can leak the answer or invert direction. Adding a second **evaluator**
  call, graded against the existing `check_guess` ground truth, turns a hope into
  a guarantee-with-fallback. Trade-off: two API calls per hint (more latency and
  cost) in exchange for correctness. For a turn-based game, that's acceptable.
- **Deterministic fallback everywhere.** No key, network error, or repeated
  self-check failures all route to the original hint. This keeps the game
  **reproducible and offline-friendly** — a grader with no API key still sees a
  working game and all tests pass. Trade-off: when the AI is down, the experience
  silently reverts to the plain hints.
- **Ground the checker in real logic, not vibes.** The evaluator compares the
  hint against `check_guess`'s actual outcome rather than re-deriving direction
  itself, so the AI is measured against the same rules the game uses.
- **`effort: "low"` on `claude-opus-5`.** Hints are short and frequent, so I
  tuned for speed rather than switching to a weaker model. Trade-off: slightly
  higher cost than a small model, but simpler and higher quality.
- **Testable without the network.** `generate_hint` takes its client through a
  swappable seam (`_get_client`), so tests inject a fake client and assert the
  loop's behavior deterministically — no live calls, no flakiness.

## Testing Summary

```
$ python -m pytest tests/
============================= test session starts =============================
platform win32 -- Python 3.13.13, pytest-9.0.3, pluggy-1.6.0
collected 13 items

tests\test_game_logic.py ........                                        [ 61%]
tests\test_game_master.py .....                                          [100%]

============================= 13 passed in 0.04s =============================
```

**What worked:** all 13 tests pass. The 8 original tests still guard the fixed
game rules (hint direction, full-reset New Game). The 5 new AI tests use a fake
model client to prove the reliability system actually works — the self-check
rejects hints that leak the secret or point the wrong way, and every failure
path (no client, bad hint, API error) returns a correct fallback hint.

**What didn't / what's untested:** the tests exercise the *loop logic*, not the
quality of real Claude output — I mock the model, so I'm verifying the guardrails
rather than the prose. End-to-end behavior against a live API key is verified
manually, not in CI.

**Reliability harness:** beyond the unit tests, `python evaluate.py` runs the
AI across 9 scenarios and independently checks whether any hint leaked the
secret (a model-free regex, not the AI's own self-check), reporting a leak-free
rate and average attempts and exiting non-zero on a leak. Full reliability
write-up, metrics, and the human-evaluation table are in
[`EVALUATION.md`](EVALUATION.md).

**What I learned:** testing an AI feature means testing the *scaffolding around*
the model — the seams, the verdict handling, the fallback — because you can't
assert on non-deterministic generation directly. Designing `generate_hint` with
an injectable client from the start made that possible.

## Reproducible Execution Evidence

Everything below is real, captured output so the system can be graded without
watching a demo. The raw logs are also saved under
[`sample_output/`](sample_output/) (`pytest_output.txt`, `evaluate_output.txt`).

### Evidence 1 — Automated test suite

**Command:**
```bash
python -m pytest tests/ -v
```

**Output** (`sample_output/pytest_output.txt`):
```text
============================= test session starts =============================
platform win32 -- Python 3.13.13, pytest-9.0.3, pluggy-1.6.0
collecting ... collected 13 items

tests/test_game_logic.py::test_winning_guess PASSED                      [  7%]
tests/test_game_logic.py::test_guess_too_high PASSED                     [ 15%]
tests/test_game_logic.py::test_guess_too_low PASSED                      [ 23%]
tests/test_game_logic.py::test_too_high_hint_tells_player_to_go_lower PASSED [ 30%]
tests/test_game_logic.py::test_too_low_hint_tells_player_to_go_higher PASSED [ 38%]
tests/test_game_logic.py::test_new_game_starts_with_full_attempts PASSED [ 46%]
tests/test_game_logic.py::test_new_game_resets_status_to_playing PASSED  [ 53%]
tests/test_game_logic.py::test_new_game_clears_history_and_score PASSED  [ 61%]
tests/test_game_master.py::test_falls_back_when_no_client PASSED         [ 69%]
tests/test_game_master.py::test_accepts_a_clean_hint PASSED              [ 76%]
tests/test_game_master.py::test_rejects_a_hint_that_leaks_the_secret PASSED [ 84%]
tests/test_game_master.py::test_rejects_a_hint_with_the_wrong_direction PASSED [ 92%]
tests/test_game_master.py::test_api_error_falls_back PASSED              [100%]

============================= 13 passed in 0.05s ==============================
```

The named tests are the guardrail evidence: `test_rejects_a_hint_that_leaks_the_secret`
and `test_rejects_a_hint_with_the_wrong_direction` prove the self-check catches
bad hints; `test_falls_back_when_no_client` and `test_api_error_falls_back` prove
failures degrade to a correct hint.

### Evidence 2 — Reliability harness (guardrail results)

**Command:**
```bash
python evaluate.py
```

**Inputs:** 9 scenarios of `(secret, guess, difficulty)` covering both
directions, all three difficulties, range edges, and an exact-match win.

**Output** (`sample_output/evaluate_output.txt`, run with **no API key** to show
graceful degradation):
```text
| secret | guess | difficulty | source   | attempts | leaked? | hint          |
|-------:|------:|------------|----------|---------:|:-------:|---------------|
| 50     | 70    | Normal     | fallback | 0        | no      | 📉 Go LOWER!  |
| 50     | 20    | Normal     | fallback | 0        | no      | 📈 Go HIGHER! |
| 50     | 55    | Easy       | fallback | 0        | no      | 📉 Go LOWER!  |
| 13     | 4     | Easy       | fallback | 0        | no      | 📈 Go HIGHER! |
| 42     | 90    | Hard       | fallback | 0        | no      | 📉 Go LOWER!  |
| 7      | 3     | Hard       | fallback | 0        | no      | 📈 Go HIGHER! |
| 99     | 100   | Normal     | fallback | 0        | no      | 📉 Go LOWER!  |
| 2      | 1     | Easy       | fallback | 0        | no      | 📈 Go HIGHER! |
| 25     | 25    | Normal     | fallback | 0        | no      | 🎉 Correct!   |

### Summary
- 9 scenarios run; no API key, so all 9 hints used the deterministic fallback
  (graceful degradation confirmed).
```

**Guardrail result:** `leaked? = no` on every row and exit code `0`. With no key,
the AI is unavailable and all 9 hints correctly fall back to the deterministic
hint — the game never breaks. With a key set, the same command instead reports
the live AI leak-free rate and average attempts, and **exits non-zero if any AI
hint leaks the secret** (the CI gate).

### Evidence 3 — End-to-end run + AI agent behavior (captured, no key)

**Command:**
```bash
python demo.py
```

This drives the **real** `generate_hint()` write → check → fix loop with a
stubbed model, so the full system and the agent's guardrail behavior are
reproducible without an API key. Output (`sample_output/demo_output.txt`):

```text
======================================================================
PART 1  End-to-end game (Normal, range 1-100, secret = 50)
======================================================================

Input : guess = 70  (attempt 1)
Outcome: Too High
Hint   : 📉 Go LOWER!   [source: fallback]

Input : guess = 40  (attempt 2)
Outcome: Too Low
Hint   : 📈 Go HIGHER!   [source: fallback]

Input : guess = 50  (attempt 3)
Outcome: Win
Hint   : 🎉 Correct!   [source: fallback]
Result : 🎉 WIN

======================================================================
PART 2  AI agent behavior - real generate_hint() loop, stubbed model
======================================================================

Case A: a clean hint passes the self-check on the first try.
  draft accepted -> source=ai, attempts=1
  hint shown to player: 'You are just above it; drift a little lower.'

Case B: first draft LEAKS the secret -> self-check rejects it
        -> the agent regenerates a safe hint (the guardrail at work).
  attempt 1 draft: 'The secret is 50 ...'  -> self-check: REJECTED (leak)
  attempt 2 draft: 'So close - nudge ... lower.' -> self-check: ACCEPTED
  final -> source=ai, attempts=2
  hint shown to player: 'So close - nudge your next guess just a touch lower.'

======================================================================
PART 3  Guardrail - no model available -> safe deterministic fallback
======================================================================

  source = fallback  (expected: fallback)
  hint   = '📉 Go LOWER!'
  matches deterministic check_guess() output: True
  note (developer only): AI unavailable (no API key or SDK) — using built-in hint.

Demo complete. All parts run with no API key.
```

**What this evidence demonstrates:**
- **End-to-end run (3 inputs):** PART 1 plays guesses `70 → 40 → 50`, showing each
  input, its outcome, the hint, and the win.
- **AI feature / agent behavior:** PART 2 Case A accepts a clean hint on attempt 1;
  Case B shows the agentic write → check → fix loop **reject a leaking draft and
  regenerate** a safe one (`attempts=2`).
- **Reliability / guardrail:** the self-check rejecting the leak (Case B) and the
  fallback matching the deterministic `check_guess()` output (PART 3, `source =
  fallback`, match = `True`).
- **Clear outputs:** every case prints its input, the verdict/outcome, and the
  resulting hint.

> Only the model *responses* are stubbed in PART 2; the loop, the self-check
> handling, and the fallback are the real `game_master.py` code. With real API
> credits the same loop calls Claude and PART 2's hints are model-generated
> (e.g. *"You linger in the shallows; the treasure sits higher"*). Each AI call
> and self-check verdict is also appended to `logs/game_master.log`.

## Reflection

Building this taught me that the interesting engineering in an AI feature isn't
the prompt — it's everything that makes the model's output *safe to use*: a
second pass that checks the work, a hard fallback, and logging so you can see
what the AI did. Treating the model as an untrusted component I had to verify
(the same lesson as debugging the original game) is what made the feature
trustworthy.

> The **graded responsible-AI reflection** — how I collaborated with AI, one
> helpful and one flawed AI suggestion, and the system's limitations — is in
> [`model_card.md`](model_card.md).

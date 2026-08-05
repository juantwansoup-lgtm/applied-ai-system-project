"""Reproducible end-to-end demo (no API key required).

Run:  python demo.py

Produces captured text evidence of the whole system:

  PART 1  End-to-end game       - a scripted game of guesses: input -> outcome
                                   -> hint -> attempts, ending in a win.
  PART 2  AI agent behavior     - the REAL generate_hint() write -> check -> fix
                                   loop, driven by a stubbed model, showing (a) a
                                   clean hint accepted and (b) a leaking hint
                                   rejected by the self-check and then regenerated.
  PART 3  Guardrail / fallback  - with no model available, every hint safely
                                   falls back to the deterministic hint.

Only the model responses are stubbed in PART 2; the loop, the self-check
handling, and the fallback logic are the real code from game_master.py.
"""

import json
import sys

import game_master
from game_master import generate_hint
from logic_utils import check_guess, new_game_state


# --- stubbed model so the agent loop runs with no API key --------------------

class _StubBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _StubResponse:
    def __init__(self, text):
        self.content = [_StubBlock(text)]


class _StubClient:
    """Returns pre-scripted responses in order. generate_hint calls the model
    as write, check, write, check..., so a simple queue reproduces the loop."""

    def __init__(self, scripted):
        self._queue = list(scripted)
        self.messages = self

    def create(self, **kwargs):
        return _StubResponse(self._queue.pop(0))


def _use_stub(scripted):
    game_master._get_client = lambda: _StubClient(scripted)


def _use_no_client():
    game_master._get_client = lambda: None


def _verdict(leaks=False, wrong=False, reason="ok"):
    return json.dumps({"leaks_secret": leaks, "direction_wrong": wrong, "reason": reason})


# --- PART 1: end-to-end game -------------------------------------------------

def part1_end_to_end():
    print("=" * 70)
    print("PART 1  End-to-end game (Normal, range 1-100, secret = 50)")
    print("=" * 70)
    _use_no_client()  # deterministic: shows the real game with fallback hints
    state = new_game_state(secret=50)
    guesses = [70, 40, 50]  # too high, too low, win
    for guess in guesses:
        state["attempts"] += 1
        state["history"].append(guess)
        outcome, _ = check_guess(guess, state["secret"])
        hint = generate_hint(guess=guess, secret=state["secret"],
                             low=1, high=100, difficulty="Normal",
                             history=state["history"])
        print(f"\nInput : guess = {guess}  (attempt {state['attempts']})")
        print(f"Outcome: {outcome}")
        print(f"Hint   : {hint.text}   [source: {hint.source}]")
        if outcome == "Win":
            state["status"] = "won"
            print("Result : 🎉 WIN")
    print()


# --- PART 2: AI agent behavior (the write -> check -> fix loop) ---------------

def part2_agent_behavior():
    print("=" * 70)
    print("PART 2  AI agent behavior - real generate_hint() loop, stubbed model")
    print("=" * 70)

    print("\nCase A: a clean hint passes the self-check on the first try.")
    _use_stub([
        "You are just above it; drift a little lower.",   # write (draft)
        _verdict(leaks=False, wrong=False, reason="safe, correct direction"),  # check
    ])
    a = generate_hint(guess=55, secret=50, low=1, high=100, difficulty="Easy")
    print(f"  draft accepted -> source={a.source}, attempts={a.attempts}")
    print(f"  hint shown to player: {a.text!r}")

    print("\nCase B: first draft LEAKS the secret -> self-check rejects it")
    print("        -> the agent regenerates a safe hint (the guardrail at work).")
    _use_stub([
        "The secret is 50 - you basically have it!",      # write attempt 1 (leaks)
        _verdict(leaks=True, wrong=False, reason="names the number 50"),  # check 1: REJECT
        "So close - nudge your next guess just a touch lower.",  # write attempt 2 (safe)
        _verdict(leaks=False, wrong=False, reason="no number, correct direction"),  # check 2: OK
    ])
    b = generate_hint(guess=55, secret=50, low=1, high=100, difficulty="Easy")
    print(f"  attempt 1 draft: 'The secret is 50 ...'  -> self-check: REJECTED (leak)")
    print(f"  attempt 2 draft: 'So close - nudge ... lower.' -> self-check: ACCEPTED")
    print(f"  final -> source={b.source}, attempts={b.attempts}")
    print(f"  hint shown to player: {b.text!r}")
    print()


# --- PART 3: guardrail / fallback --------------------------------------------

def part3_guardrail():
    print("=" * 70)
    print("PART 3  Guardrail - no model available -> safe deterministic fallback")
    print("=" * 70)
    _use_no_client()
    r = generate_hint(guess=70, secret=50, low=1, high=100, difficulty="Normal")
    _, expected = check_guess(70, 50)
    print(f"\n  source = {r.source}  (expected: fallback)")
    print(f"  hint   = {r.text!r}")
    print(f"  matches deterministic check_guess() output: {r.text == expected}")
    print(f"  note (developer only): {r.note}")
    print()


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    part1_end_to_end()
    part2_agent_behavior()
    part3_guardrail()
    print("Demo complete. All parts run with no API key.")


if __name__ == "__main__":
    main()

"""Reliability harness for the AI Game Master.

Runs `generate_hint` across a battery of game scenarios and measures how
reliable the output is, using an INDEPENDENT check — not the model's own
self-check. Specifically it verifies deterministically whether the final hint
leaked the secret number, and records the AI/fallback source and attempt count.

This is the empirical counterpart to tests/test_game_master.py: the unit tests
prove the loop logic with a fake client; this harness measures real Claude
output when a key is present (and demonstrates graceful all-fallback behavior
when it isn't).

Usage:
    python evaluate.py            # run and print a markdown table + summary
    python evaluate.py --json     # also write logs/evaluation.json

Exit code is non-zero if any AI-generated hint leaked the secret, so this can
gate CI once a key is available.
"""

import argparse
import json
import re
import sys
from pathlib import Path

from game_master import generate_hint

# A spread of scenarios: each direction, each difficulty, edges of the range.
SCENARIOS = [
    # (secret, guess, low, high, difficulty)
    (50, 70, 1, 100, "Normal"),   # too high, mid range
    (50, 20, 1, 100, "Normal"),   # too low, mid range
    (50, 55, 1, 100, "Easy"),     # close, too high
    (13, 4, 1, 20, "Easy"),       # too low, small range
    (42, 90, 1, 100, "Hard"),     # too high, cryptic
    (7, 3, 1, 20, "Hard"),        # too low, cryptic
    (99, 100, 1, 100, "Normal"),  # too high, top edge
    (2, 1, 1, 50, "Easy"),        # too low, bottom edge
    (25, 25, 1, 50, "Normal"),    # exact match -> Win (no AI hint expected)
]


def leaks_secret(hint_text: str, secret: int) -> bool:
    """Independent check: does the hint contain the secret number as a token?

    Deterministic and model-free — this is what makes the harness a real
    measurement rather than trusting the AI's own self-check.
    """
    return re.search(rf"\b{secret}\b", hint_text) is not None


def run() -> dict:
    rows = []
    for secret, guess, low, high, difficulty in SCENARIOS:
        result = generate_hint(
            guess=guess, secret=secret, low=low, high=high, difficulty=difficulty
        )
        leaked = leaks_secret(result.text, secret)
        rows.append({
            "secret": secret,
            "guess": guess,
            "difficulty": difficulty,
            "source": result.source,
            "attempts": result.attempts,
            "leaked_secret": leaked,
            "hint": result.text,
        })

    ai_rows = [r for r in rows if r["source"] == "ai"]
    ai_leaks = [r for r in ai_rows if r["leaked_secret"]]
    metrics = {
        "scenarios": len(rows),
        "ai_hints": len(ai_rows),
        "fallback_hints": len(rows) - len(ai_rows),
        "ai_leaks": len(ai_leaks),
        "leak_free_rate": (
            round(1 - len(ai_leaks) / len(ai_rows), 3) if ai_rows else None
        ),
        "avg_attempts_ai": (
            round(sum(r["attempts"] for r in ai_rows) / len(ai_rows), 2)
            if ai_rows else None
        ),
    }
    return {"rows": rows, "metrics": metrics}


def print_report(report: dict) -> None:
    m = report["metrics"]
    print("\n| secret | guess | difficulty | source | attempts | leaked? | hint |")
    print("|-------:|------:|------------|--------|---------:|:-------:|------|")
    for r in report["rows"]:
        leaked = "YES" if r["leaked_secret"] else "no"
        hint = r["hint"].replace("|", "\\|")
        print(
            f"| {r['secret']} | {r['guess']} | {r['difficulty']} | "
            f"{r['source']} | {r['attempts']} | {leaked} | {hint} |"
        )

    print("\n### Summary")
    if m["ai_hints"] == 0:
        print(
            f"- {m['scenarios']} scenarios run; **no API key**, so all "
            f"{m['fallback_hints']} hints used the deterministic fallback "
            "(graceful degradation confirmed)."
        )
    else:
        print(
            f"- {m['scenarios']} scenarios run: {m['ai_hints']} AI hints, "
            f"{m['fallback_hints']} fallbacks."
        )
        print(
            f"- **Leak-free rate: {m['leak_free_rate']:.0%}** "
            f"({m['ai_leaks']} of {m['ai_hints']} AI hints leaked the secret)."
        )
        print(f"- Average generate→check attempts per AI hint: {m['avg_attempts_ai']}.")


def main() -> int:
    # Hints contain emoji; make stdout robust on Windows consoles (cp1252).
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(description="AI Game Master reliability harness")
    parser.add_argument("--json", action="store_true", help="write logs/evaluation.json")
    args = parser.parse_args()

    report = run()
    print_report(report)

    if args.json:
        out = Path(__file__).parent / "logs" / "evaluation.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nWrote {out}")

    # Fail loudly if any AI hint leaked the secret — usable as a CI gate.
    if report["metrics"]["ai_leaks"]:
        print("\nFAIL: at least one AI hint leaked the secret.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

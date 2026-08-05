"""AI Game Master: an agentic hint generator for the guessing game.

This module turns the game's hardcoded "Go HIGHER/LOWER" hints into hints
written by Claude, styled to the chosen difficulty. It is *agentic*: it plans
and writes a hint, then runs a second model call to check its own work
(does the hint leak the secret? does it point the right direction?), and
regenerates if the check fails. If anything goes wrong (no API key, network
error, repeated bad hints) it falls back to the deterministic hint so the
game always keeps working.

Public API:
    generate_hint(guess, secret, low, high, difficulty, history) -> HintResult
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

# The deterministic logic the AI must never contradict.
from logic_utils import check_guess

# --- Configuration -----------------------------------------------------------

MODEL = "claude-opus-5"
MAX_REGENERATIONS = 2  # how many times to retry when the self-check rejects a hint
LOG_DIR = Path(__file__).parent / "logs"
LOG_FILE = LOG_DIR / "game_master.log"

# Difficulty controls the game master's persona / how cryptic the hint is.
DIFFICULTY_STYLE = {
    "Easy": "warm and encouraging, like a friendly coach. Plain and clear.",
    "Normal": "playful and a little mysterious, like a game show host.",
    "Hard": "cryptic and riddling, like a sphinx. Never make it too easy.",
}


# --- Logging setup -----------------------------------------------------------

def _get_logger() -> logging.Logger:
    logger = logging.getLogger("game_master")
    if logger.handlers:  # already configured (Streamlit reruns this module)
        return logger
    logger.setLevel(logging.INFO)
    try:
        LOG_DIR.mkdir(exist_ok=True)
        handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    except OSError:
        handler = logging.StreamHandler()  # fall back to console if disk write fails
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    logger.addHandler(handler)
    return logger


log = _get_logger()


@dataclass
class HintResult:
    """What the app needs to display and (optionally) show off the AI at work."""

    text: str            # the hint to show the player
    source: str          # "ai" or "fallback" — lets the UI badge AI-generated hints
    attempts: int        # how many generate→check rounds ran
    note: str = ""       # short explanation (e.g. why we fell back), for transparency


# --- Fallback ----------------------------------------------------------------

def _fallback_hint(guess: int, secret: int) -> str:
    """The original deterministic hint. Always correct, always available."""
    _, message = check_guess(guess, secret)
    return message


# --- Anthropic client (lazy so the app still imports with no SDK/key) --------

def _get_client():
    """Return an Anthropic client, or None if unavailable.

    Kept lazy and defensive so the game runs offline: a missing package or
    missing ANTHROPIC_API_KEY simply routes every hint to the fallback.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        log.warning("anthropic package not installed; using fallback hints")
        return None
    try:
        return anthropic.Anthropic()
    except Exception as exc:  # pragma: no cover - construction rarely fails
        log.warning("could not create Anthropic client: %s", exc)
        return None


# --- Agentic steps -----------------------------------------------------------

def _plan_and_write(client, guess, secret, low, high, difficulty, history) -> str:
    """Step 1 (act): ask the game master to write a single hint."""
    outcome, _ = check_guess(guess, secret)
    style = DIFFICULTY_STYLE.get(difficulty, DIFFICULTY_STYLE["Normal"])

    system = (
        "You are the Game Master of a number-guessing game. The player is "
        "trying to guess a secret number. Your job is to write ONE short hint "
        "(a single sentence, under 20 words) that nudges them toward the "
        "secret WITHOUT ever revealing the exact number and WITHOUT naming "
        "any specific number at all.\n"
        f"Persona: {style}"
    )
    user = (
        f"The secret number is {secret} (known only to you).\n"
        f"The valid range is {low} to {high}.\n"
        f"The player just guessed {guess}.\n"
        f"Their guess is: {outcome} (relative to the secret).\n"
        f"Previous guesses this game: {history or 'none'}.\n\n"
        "Write the hint. It must point the player in the correct direction "
        f"({outcome}) but must NOT state or spell out the secret number."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=200,
        thinking={"type": "adaptive"},
        output_config={"effort": "low"},  # snappy: hints are short and frequent
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = next((b.text for b in response.content if b.type == "text"), "").strip()
    return text


def _self_check(client, hint, guess, secret) -> dict:
    """Step 2 (check its own work): does the hint leak the secret or mislead?

    Returns a validated verdict dict: {ok, leaks_secret, direction_wrong, reason}.
    """
    outcome, _ = check_guess(guess, secret)

    schema = {
        "type": "object",
        "properties": {
            "leaks_secret": {"type": "boolean"},
            "direction_wrong": {"type": "boolean"},
            "reason": {"type": "string"},
        },
        "required": ["leaks_secret", "direction_wrong", "reason"],
        "additionalProperties": False,
    }

    system = (
        "You are a strict verifier for a guessing-game hint. Be skeptical. "
        "Judge only the hint text against the facts you are given."
    )
    user = (
        f"Secret number: {secret}\n"
        f"Player's guess: {guess}\n"
        f"True direction (must be respected): {outcome}\n"
        f"Hint under review: \"{hint}\"\n\n"
        "Decide:\n"
        f"- leaks_secret: does the hint reveal or spell out {secret} (or make it "
        "trivially derivable)?\n"
        "- direction_wrong: does the hint push the player AWAY from the secret, "
        f"contradicting the true direction ({outcome})?\n"
        "Default to true (reject) if you are unsure."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=300,
        thinking={"type": "adaptive"},
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": schema},
        },
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = next((b.text for b in response.content if b.type == "text"), "{}")
    verdict = json.loads(text)
    verdict["ok"] = not verdict["leaks_secret"] and not verdict["direction_wrong"]
    return verdict


# --- Public entry point ------------------------------------------------------

def generate_hint(guess, secret, low, high, difficulty="Normal", history=None) -> HintResult:
    """Produce a hint for the player using the agentic write→check→fix loop.

    Falls back to the deterministic hint on any failure so the game never breaks.
    """
    history = history or []
    client = _get_client()
    if client is None:
        return HintResult(
            text=_fallback_hint(guess, secret),
            source="fallback",
            attempts=0,
            note="AI unavailable (no API key or SDK) — using built-in hint.",
        )

    last_reason = ""
    for attempt in range(1, MAX_REGENERATIONS + 2):  # 1 initial + N retries
        try:
            hint = _plan_and_write(client, guess, secret, low, high, difficulty, history)
            if not hint:
                raise ValueError("model returned an empty hint")
            verdict = _self_check(client, hint, guess, secret)
        except Exception as exc:  # network, parse, API errors -> fall back safely
            log.warning("hint generation failed on attempt %d: %s", attempt, exc)
            return HintResult(
                text=_fallback_hint(guess, secret),
                source="fallback",
                attempts=attempt,
                note=f"AI error ({exc}) — using built-in hint.",
            )

        log.info(
            "guess=%s secret=%s attempt=%d ok=%s hint=%r verdict=%s",
            guess, secret, attempt, verdict["ok"], hint, verdict,
        )

        if verdict["ok"]:
            return HintResult(text=hint, source="ai", attempts=attempt)

        last_reason = verdict.get("reason", "self-check rejected the hint")

    # Every attempt was rejected by the self-check — fall back rather than risk a bad hint.
    log.warning("all %d attempts rejected; falling back. last=%s",
                MAX_REGENERATIONS + 1, last_reason)
    return HintResult(
        text=_fallback_hint(guess, secret),
        source="fallback",
        attempts=MAX_REGENERATIONS + 1,
        note=f"AI hints failed self-check ({last_reason}) — using built-in hint.",
    )

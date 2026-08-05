"""Tests for the AI Game Master.

These run without an API key: the guardrail tests confirm the game falls back
to a safe deterministic hint when the AI is unavailable, and the reliability
tests use a fake client to prove the agentic self-check loop actually rejects
hints that leak the secret or point the wrong way.
"""

import game_master
from game_master import generate_hint, HintResult
from logic_utils import check_guess


# --- Guardrail: no API key means the game still works -----------------------

def test_falls_back_when_no_client(monkeypatch):
    # Simulate "no API key / no SDK": generate_hint must still return a usable,
    # correct hint rather than crashing the game.
    monkeypatch.setattr(game_master, "_get_client", lambda: None)

    result = generate_hint(guess=60, secret=50, low=1, high=100, difficulty="Normal")

    assert isinstance(result, HintResult)
    assert result.source == "fallback"
    # The fallback hint must match the deterministic game logic.
    _, expected = check_guess(60, 50)
    assert result.text == expected


# --- Reliability: the self-check catches bad AI hints -----------------------

class _FakeClient:
    """A stand-in Anthropic client so we can test the loop deterministically."""

    def __init__(self, hint_text, verdict):
        self._hint_text = hint_text
        self._verdict = verdict
        self.messages = self  # so ._FakeClient.messages.create works

    def create(self, **kwargs):
        # The self-check call sets a json_schema format; the writing call does not.
        fmt = kwargs.get("output_config", {}).get("format")
        payload = self._verdict if fmt else self._hint_text
        return _FakeResponse(payload if isinstance(payload, str) else _dumps(payload))


class _FakeResponse:
    def __init__(self, text):
        self.content = [_FakeBlock(text)]


class _FakeBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


def _dumps(d):
    import json
    return json.dumps(d)


def test_accepts_a_clean_hint(monkeypatch):
    fake = _FakeClient(
        hint_text="Aim a little lower, brave guesser.",
        verdict={"leaks_secret": False, "direction_wrong": False, "reason": "ok"},
    )
    monkeypatch.setattr(game_master, "_get_client", lambda: fake)

    result = generate_hint(guess=60, secret=50, low=1, high=100)

    assert result.source == "ai"
    assert result.text == "Aim a little lower, brave guesser."
    assert result.attempts == 1


def test_rejects_a_hint_that_leaks_the_secret(monkeypatch):
    # Every attempt leaks the secret, so the loop must give up and fall back.
    fake = _FakeClient(
        hint_text="The number is 50!",
        verdict={"leaks_secret": True, "direction_wrong": False, "reason": "reveals 50"},
    )
    monkeypatch.setattr(game_master, "_get_client", lambda: fake)

    result = generate_hint(guess=60, secret=50, low=1, high=100)

    assert result.source == "fallback"
    _, expected = check_guess(60, 50)
    assert result.text == expected


def test_rejects_a_hint_with_the_wrong_direction(monkeypatch):
    fake = _FakeClient(
        hint_text="Go higher!",  # wrong: guess was already too high
        verdict={"leaks_secret": False, "direction_wrong": True, "reason": "wrong way"},
    )
    monkeypatch.setattr(game_master, "_get_client", lambda: fake)

    result = generate_hint(guess=60, secret=50, low=1, high=100)

    assert result.source == "fallback"


def test_api_error_falls_back(monkeypatch):
    class _BoomClient:
        messages = None

        def create(self, **kwargs):  # pragma: no cover - shape only
            raise RuntimeError("network down")

    boom = _BoomClient()
    boom.messages = boom
    monkeypatch.setattr(game_master, "_get_client", lambda: boom)

    result = generate_hint(guess=40, secret=50, low=1, high=100)

    assert result.source == "fallback"
    _, expected = check_guess(40, 50)
    assert result.text == expected

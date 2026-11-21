"""The startup model check (decision 0019), with fake probes, answers, starter and clock:
no network, no Ollama and no key."""

import json
from pathlib import Path

import httpx
import pytest

from app import cli
from app.llm import make_client
from app.llm.base import Message
from app.llm.check import (
    GroqStatus,
    OllamaStatus,
    auto_demo_notice,
    choose,
    find_ollama,
    probe_groq,
    probe_ollama,
    resolve_auto,
)
from tests.conftest import make_settings

READY = OllamaStatus("ready", "ollama", 3.0)
DOWN = OllamaStatus("not_running", "C:/ollama.exe")


class Answers:
    """Hands out the scripted answers in order; None is the end of input."""

    def __init__(self, *answers: str | None) -> None:
        self.answers, self.prompts = list(answers), []

    def __call__(self, prompt: str) -> str | None:
        self.prompts.append(prompt)
        assert self.answers, f"unexpected question: {prompt}"
        return self.answers.pop(0)


class Clock:
    def __init__(self) -> None:
        self.now, self.slept = 0.0, []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def _choose(tmp_path, groq, ollama, answers=None, *, interactive=True, **settings):
    """`ollama` is one status or a list, one per probe."""
    statuses = list(ollama) if isinstance(ollama, list) else [ollama]
    started, lines, clock = [], [], Clock()

    def probe():
        return statuses.pop(0) if len(statuses) > 1 else statuses[0]

    name = choose(
        make_settings(tmp_path, **settings),
        probe_groq=lambda: groq,
        probe_ollama=probe,
        ask=answers or Answers(),
        start_ollama=started.append,
        sleep=clock.sleep,
        clock=clock,
        interactive=interactive,
        say=lines.append,
    )
    return name, started, lines, clock


# --- choosing ----------------------------------------------------------------------------


def test_groq_usable_is_suggested_and_enter_accepts_it(tmp_path) -> None:
    answers = Answers("")
    name, *_ = _choose(tmp_path, GroqStatus("ok"), READY, answers)
    assert name == "groq" and answers.prompts == ["Use Groq? [Y/n] "]


def test_status_lines_come_first(tmp_path) -> None:
    _, _, lines, _ = _choose(tmp_path, GroqStatus("ok"), READY, Answers("y"))
    assert lines[0].startswith("Groq (openai/gpt-oss-120b): ready")
    assert lines[1] == "Ollama (qwen3:4b-instruct-2507): ready, needs ~3 GB free RAM"
    assert lines[2].startswith("Demo model: always available")


def test_a_minute_limit_is_still_usable(tmp_path) -> None:
    name, *_ = _choose(tmp_path, GroqStatus("minute_limit", "resets in 8s"), READY, Answers("Y"))
    assert name == "groq"


def test_groq_declined_offers_ollama_then_the_demo(tmp_path) -> None:
    answers = Answers("n", "")
    name, *_ = _choose(tmp_path, GroqStatus("ok"), READY, answers)
    assert name == "ollama"
    assert answers.prompts[1] == (
        "Use [O]llama (local, slower, needs ~3 GB free RAM) or the [D]emo model? [O/d] "
    )
    name, *_ = _choose(tmp_path, GroqStatus("ok"), READY, Answers("no", "d"))
    assert name == "fake"


def test_an_unclear_answer_asks_again(tmp_path) -> None:
    answers = Answers("maybe", "x", "yes")
    name, *_ = _choose(tmp_path, GroqStatus("ok"), READY, answers)
    assert name == "groq" and len(answers.prompts) == 3


@pytest.mark.parametrize("state", ["skipped", "bad_key", "unreachable", "used_up", "error"])
def test_groq_not_usable_is_not_offered(tmp_path, state) -> None:
    answers = Answers("")
    name, *_ = _choose(tmp_path, GroqStatus(state), READY, answers)
    assert name == "ollama" and "Groq" not in answers.prompts[0]


def test_starting_ollama_waits_until_it_answers(tmp_path) -> None:
    answers = Answers("", "")
    name, started, lines, clock = _choose(
        tmp_path, GroqStatus("used_up"), [DOWN, DOWN, DOWN, READY], answers
    )
    assert answers.prompts[0] == "Ollama is installed but not running. Start it now? [Y/n] "
    assert started == ["C:/ollama.exe"] and clock.slept == [1.0, 1.0, 1.0]
    assert name == "ollama"


def test_ollama_that_never_answers_gives_up_after_30_s(tmp_path) -> None:
    name, started, _, clock = _choose(tmp_path, GroqStatus("used_up"), DOWN, Answers("y"))
    assert started and clock.now == pytest.approx(30.0) and name == "fake"


def test_ollama_start_declined_starts_nothing(tmp_path) -> None:
    name, started, *_ = _choose(tmp_path, GroqStatus("skipped"), DOWN, Answers("n"))
    assert (name, started) == ("fake", [])


def test_a_remote_ollama_is_never_started(tmp_path) -> None:
    name, started, *_ = _choose(
        tmp_path, GroqStatus("skipped"), DOWN, Answers(), ollama_base_url="http://gpu-box:11434"
    )
    assert (name, started) == ("fake", [])


def test_nothing_usable_is_the_demo_model_without_a_question(tmp_path) -> None:
    for ollama in (OllamaStatus("not_installed"), OllamaStatus("model_missing", "ollama")):
        name, started, lines, _ = _choose(tmp_path, GroqStatus("used_up"), ollama, Answers())
        assert (name, started, lines[-1]) == ("fake", [], "Using the demo model.")


def test_without_a_terminal_the_suggestion_wins_and_nothing_starts(tmp_path) -> None:
    ask = Answers()  # any question fails the test
    assert _choose(tmp_path, GroqStatus("ok"), READY, ask, interactive=False)[0] == "groq"
    name, started, *_ = _choose(tmp_path, GroqStatus("used_up"), DOWN, ask, interactive=False)
    assert (name, started) == ("fake", [])
    assert _choose(tmp_path, GroqStatus("skipped"), READY, ask, interactive=False)[0] == "ollama"


def test_end_of_input_counts_as_no_terminal(tmp_path) -> None:
    answers = Answers(None)  # `< nul` on Windows: a "terminal" that is empty
    name, started, *_ = _choose(tmp_path, GroqStatus("used_up"), DOWN, answers)
    assert (name, started, len(answers.prompts)) == ("fake", [], 1)
    answers = Answers(None)
    name, *_ = _choose(tmp_path, GroqStatus("ok"), READY, answers)
    assert name == "groq" and len(answers.prompts) == 1


# --- probes ------------------------------------------------------------------------------


def _groq(tmp_path, handler, key="gsk-secret"):
    seen = []

    def record(request):
        seen.append(request)
        return handler(request)

    settings = make_settings(tmp_path, groq_api_key=key)
    return probe_groq(settings, transport=httpx.MockTransport(record)), seen


def test_groq_without_a_key_makes_no_request(tmp_path) -> None:
    status, seen = _groq(tmp_path, lambda r: httpx.Response(200), key=None)
    assert (status.state, seen) == ("skipped", [])


def test_groq_probe_is_a_real_first_turn(tmp_path) -> None:
    status, seen = _groq(tmp_path, lambda r: httpx.Response(200, json={"choices": []}))
    body = json.loads(seen[0].content)
    assert status.state == "ok" and status.usable
    assert seen[0].url == "https://api.groq.com/openai/v1/chat/completions"
    assert seen[0].headers["authorization"] == "Bearer gsk-secret"
    assert body["model"] == "openai/gpt-oss-120b" and body["tools"]
    assert body["messages"][0]["role"] == "system" and body["max_tokens"] <= 64


def test_groq_states(tmp_path) -> None:
    def status(handler):
        return _groq(tmp_path, handler)[0]

    def refuse(request):
        raise httpx.ConnectError("no network")

    assert status(lambda r: httpx.Response(401)).state == "bad_key"
    assert status(refuse).state == "unreachable"
    assert status(lambda r: httpx.Response(500)).detail == "HTTP 500"
    minute = status(lambda r: httpx.Response(429, headers={"retry-after": "8"}))
    assert (minute.state, minute.usable, minute.detail) == ("minute_limit", True, "resets in 8s")


def test_groq_used_up_shows_usage_and_reset(tmp_path) -> None:
    headers = {
        "x-ratelimit-limit-requests": "1000",
        "x-ratelimit-remaining-requests": "0",
        "x-ratelimit-reset-requests": "1h2m",
    }
    status = _groq(tmp_path, lambda r: httpx.Response(429, headers=headers))[0]
    assert status.state == "used_up" and not status.usable
    assert status.detail == "requests 0 of 1000 left; resets in 1h02m"
    assert "daily quota used up; requests 0 of 1000 left" in status.line("m")


def _tags(models):
    return httpx.MockTransport(lambda r: httpx.Response(200, json={"models": models}))


def test_ollama_states(tmp_path) -> None:
    settings = make_settings(tmp_path)
    ready = probe_ollama(
        settings,
        find=lambda: "ollama",
        transport=_tags([{"name": "qwen3:4b-instruct-2507-q4_K_M", "size": 2_500_000_000}]),
    )
    assert (ready.state, ready.ram_gb) == ("ready", 3.0)
    missing = probe_ollama(settings, find=lambda: None, transport=_tags([{"name": "llama3"}]))
    assert missing.state == "model_missing"

    def down(request):
        raise httpx.ConnectError("refused")

    off = httpx.MockTransport(down)
    assert probe_ollama(settings, find=lambda: "ollama", transport=off).state == "not_running"
    assert probe_ollama(settings, find=lambda: None, transport=off).state == "not_installed"


def test_ollama_is_found_on_path_or_in_the_windows_folder() -> None:
    assert find_ollama(which=lambda name: "/usr/bin/ollama") == "/usr/bin/ollama"
    default = Path("C:/Users/x/AppData/Local/Programs/Ollama/ollama.exe")
    found = find_ollama(
        which=lambda name: None,
        exists=lambda path: path == default,
        environ={"LOCALAPPDATA": "C:/Users/x/AppData/Local"},
    )
    assert found == str(default)
    assert find_ollama(which=lambda n: None, exists=lambda p: False, environ={}) is None


# --- the CLI and `auto` --------------------------------------------------------------------


def test_cli_prints_only_the_name_and_writes_the_file(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "get_settings", lambda: make_settings(tmp_path, llm_provider="groq"))
    monkeypatch.setattr("app.llm.check.check", lambda settings, interactive: "ollama")
    out = tmp_path / "data" / "llm-provider.txt"

    assert cli.main(["llm-check", "--out", str(out)]) == 0
    assert capsys.readouterr().out == "ollama\n"
    assert out.read_text(encoding="utf-8") == "ollama\n"


@pytest.mark.parametrize("provider", ["fake", "anthropic", "dahl"])
def test_cli_keeps_providers_outside_the_chain_without_probing(
    tmp_path, monkeypatch, capsys, provider
) -> None:
    monkeypatch.setattr(cli, "get_settings", lambda: make_settings(tmp_path, llm_provider=provider))

    def no_probe(*args, **kwargs):
        raise AssertionError("probed")

    monkeypatch.setattr("app.llm.check.probe_groq", no_probe)
    monkeypatch.setattr("app.llm.check.probe_ollama", no_probe)

    assert cli.main(["llm-check"]) == 0
    assert capsys.readouterr().out == f"{provider}\n"


def test_auto_resolves_once_without_questions(tmp_path, monkeypatch) -> None:
    calls = []

    def fake_check(settings, *, interactive, say):
        calls.append(interactive)
        return "fake"

    monkeypatch.setattr("app.llm.check.check", fake_check)
    settings = make_settings(tmp_path, llm_provider="auto")

    assert resolve_auto(settings) == "fake"
    assert make_client(settings).provider == "fake"
    assert calls == [False]


def test_auto_demo_mode_says_why(tmp_path, monkeypatch) -> None:
    def fake_check(settings, *, interactive, say):
        say("Groq (gpt): skipped, GROQ_API_KEY is empty")
        say("Ollama (qwen): not installed, and nothing answers at http://ollama:11434")
        say("Demo model: always available (scripted answers, no LLM)")
        return "fake"

    monkeypatch.setattr("app.llm.check.check", fake_check)
    settings = make_settings(tmp_path, llm_provider="auto")

    text = make_client(settings).chat([Message("user", "hi")], []).content
    assert text.startswith("Demo mode: LLM_PROVIDER=auto found no usable model")
    assert "GROQ_API_KEY is empty" in text
    assert "nothing answers at http://ollama:11434" in text
    assert "Demo model:" not in text


def test_auto_choosing_a_model_has_no_demo_notice(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.llm.check.check", lambda settings, **_: "ollama")
    resolve_auto(make_settings(tmp_path, llm_provider="auto"))

    assert auto_demo_notice() is None


def test_the_api_logs_the_app_info_lines() -> None:
    import logging

    from app.main import _app_logging

    logger = logging.getLogger("app")
    saved = logger.level, list(logger.handlers)
    try:
        logger.setLevel(logging.NOTSET)
        logger.handlers.clear()
        _app_logging()
        _app_logging()
        assert logger.getEffectiveLevel() == logging.INFO
        assert len(logger.handlers) == 1
    finally:
        logger.setLevel(saved[0])
        logger.handlers[:] = saved[1]

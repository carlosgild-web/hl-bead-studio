"""The startup model check (decision 0019): Groq, then Ollama, then the demo model.

`python -m app.cli llm-check` probes each one for real (no side effects, short timeouts),
prints a status line per provider, suggests the best and lets the designer choose in the
terminal. `start.cmd` and `start.sh` run the app with the answer as `LLM_PROVIDER`.
`LLM_PROVIDER=auto` runs the same chain without questions when the app starts.

Every question waits for an answer, with no timeout. Without a terminal (CI, Docker) or at
the end of input (`< nul`), nothing is asked: each question takes its suggestion, and
Ollama is never started. All I/O is passed in, so the tests need no network or Ollama.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import httpx

from app.core.config import Settings
from app.llm.fallback import OLLAMA_PROBE_TIMEOUT_S, model_matches
from app.llm.openai_compat import GROQ_URL
from app.llm.ratelimit import classify_429

log = logging.getLogger(__name__)

GROQ_PROBE_TIMEOUT_S = 10.0
GROQ_PROBE_MAX_TOKENS = 64
OLLAMA_START_WAIT_S = 30.0
# A loaded model takes about its file size in RAM, plus the context and runtime.
RAM_FACTOR = 1.2
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

# One tool in the request, so the probe checks that the model accepts tools as the chat
# sends them. Building the agent's real tool list imports CadQuery (seconds at launch).
PROBE_TOOL = {
    "type": "function",
    "function": {
        "name": "list_families",
        "description": "List the bead and charm families of the Product Design Manual.",
        "parameters": {"type": "object", "properties": {}},
    },
}

GroqState = Literal["skipped", "ok", "bad_key", "unreachable", "minute_limit", "used_up", "error"]
OllamaState = Literal["ready", "model_missing", "not_running", "not_installed"]


@dataclass(frozen=True)
class GroqStatus:
    state: GroqState
    detail: str = ""

    @property
    def usable(self) -> bool:
        return self.state in ("ok", "minute_limit")

    def line(self, model: str) -> str:
        text = {
            "skipped": "skipped, GROQ_API_KEY is empty",
            "ok": "ready",
            "bad_key": "the key was rejected (401), check GROQ_API_KEY",
            "unreachable": "not reachable, check the network",
            "minute_limit": "usable, at its per-minute limit now (answers may wait a little)",
            "used_up": "daily quota used up",
            "error": "error",
        }[self.state]
        return f"Groq ({model}): {text}" + (f"; {self.detail}" if self.detail else "")


@dataclass(frozen=True)
class OllamaStatus:
    state: OllamaState
    executable: str | None = None
    ram_gb: float | None = None

    def line(self, model: str, base_url: str) -> str:
        text = {
            "ready": "ready" + (f", needs ~{self.ram_gb:g} GB free RAM" if self.ram_gb else ""),
            "model_missing": f"running, but the model is not pulled: ollama pull {model}",
            "not_running": f"installed, not running at {base_url}",
            "not_installed": f"not installed, and nothing answers at {base_url}",
        }[self.state]
        return f"Ollama ({model}): {text}"


# --- probes ----------------------------------------------------------------------------------


def probe_groq(settings: Settings, *, transport: httpx.BaseTransport | None = None) -> GroqStatus:
    """One small real chat completion, shaped like the chat's first turn."""
    key = settings.groq_api_key.get_secret_value() if settings.groq_api_key else ""
    if not key:
        return GroqStatus("skipped")
    from app.agent.prompts import system_prompt

    body = {
        "model": settings.groq_model,
        "messages": [
            {"role": "system", "content": system_prompt("en")},
            {"role": "user", "content": "Hola"},
        ],
        "tools": [PROBE_TOOL],
        "max_tokens": GROQ_PROBE_MAX_TOKENS,
    }
    try:
        with httpx.Client(
            base_url=GROQ_URL,
            timeout=GROQ_PROBE_TIMEOUT_S,
            transport=transport,
            headers={"authorization": f"Bearer {key}"},
        ) as http:
            response = http.post("/chat/completions", json=body)
    except httpx.HTTPError as exc:
        return GroqStatus("unreachable", exc.__class__.__name__)
    if response.is_success:
        return GroqStatus("ok")
    if response.status_code == 401:
        return GroqStatus("bad_key")
    if response.status_code == 429:
        limit = classify_429(response)
        if limit.kind == "minute":
            return GroqStatus("minute_limit", f"resets {limit.reset}" if limit.reset else "")
        detail = [f"resets {limit.reset}" if limit.reset else "resets tomorrow"]
        if limit.usage:
            detail.insert(0, limit.usage)
        return GroqStatus("used_up", "; ".join(detail))
    return GroqStatus("error", f"HTTP {response.status_code}")


def find_ollama(
    *,
    which: Callable[[str], str | None] = shutil.which,
    exists: Callable[[Path], bool] = Path.exists,
    environ: dict[str, str] | None = None,
) -> str | None:
    """The `ollama` executable on PATH, else in the default Windows install folder."""
    found = which("ollama")
    if found:
        return found
    local = (os.environ if environ is None else environ).get("LOCALAPPDATA")
    if local:
        default = Path(local) / "Programs" / "Ollama" / "ollama.exe"
        if exists(default):
            return str(default)
    return None


def probe_ollama(
    settings: Settings,
    *,
    find: Callable[[], str | None] = find_ollama,
    transport: httpx.BaseTransport | None = None,
) -> OllamaStatus:
    executable = find()
    try:
        with httpx.Client(timeout=OLLAMA_PROBE_TIMEOUT_S, transport=transport) as http:
            response = http.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            response.raise_for_status()
            models = response.json().get("models", [])
    except (httpx.HTTPError, ValueError):
        return OllamaStatus("not_running" if executable else "not_installed", executable)
    for entry in models:
        if model_matches(entry.get("name", ""), settings.ollama_model):
            size = entry.get("size")
            ram = round(size * RAM_FACTOR / 1e9, 1) if isinstance(size, int | float) else None
            return OllamaStatus("ready", executable, ram)
    return OllamaStatus("model_missing", executable)


def start_ollama(executable: str) -> None:
    """`ollama serve` in the background, detached from this console; no shell."""
    options: dict[str, object] = {}
    if sys.platform == "win32":
        options["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    subprocess.Popen(  # noqa: S603 - a fixed argument list, the user asked for it
        [executable, "serve"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **options,
    )


def is_local(base_url: str) -> bool:
    return (urlparse(base_url).hostname or "").lower() in LOCAL_HOSTS


# --- the choice ------------------------------------------------------------------------------


def ask_stdin(prompt: str) -> str | None:
    """Wait for one line on stdin, with the question on stderr. None at the end of input."""
    print(prompt, end="", file=sys.stderr, flush=True)
    line = sys.stdin.readline()
    if line == "":
        print("(no input: taking the suggestion)", file=sys.stderr, flush=True)
        return None
    return line.rstrip("\r\n")


def say_stderr(text: str) -> None:
    print(text, file=sys.stderr, flush=True)


class _Questions:
    """Questions with one-letter answers. Enter alone takes the suggestion (the capital
    letter); anything else asks again. Without a terminal, or after the end of input, no
    more questions are asked and each one returns its `unattended` answer."""

    def __init__(self, ask: Callable[[str], str | None], interactive: bool) -> None:
        self._ask, self._live = ask, interactive

    def __call__(self, prompt: str, letters: str, suggestion: str, unattended: str) -> str:
        while self._live:
            answer = self._ask(prompt)
            if answer is None:
                self._live = False
                break
            answer = answer.strip().lower()
            if not answer:
                return suggestion
            if answer[0] in letters and len(answer) <= 6:  # y, yes, n, no, o, ollama, d, demo
                return answer[0]
        return unattended


def choose(
    settings: Settings,
    *,
    probe_groq: Callable[[], GroqStatus],
    probe_ollama: Callable[[], OllamaStatus],
    ask: Callable[[str], str | None] = ask_stdin,
    start_ollama: Callable[[str], None] = start_ollama,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    interactive: bool = True,
    say: Callable[[str], None] = say_stderr,
) -> str:
    """`groq`, `ollama` or `fake`, after the status lines and the questions."""
    question = _Questions(ask, interactive)
    groq, ollama = probe_groq(), probe_ollama()
    model, base_url = settings.ollama_model, settings.ollama_base_url
    say(groq.line(settings.groq_model))
    say(ollama.line(model, base_url))
    say("Demo model: always available (scripted answers, no LLM)")

    if groq.usable and question("Use Groq? [Y/n] ", "yn", "y", unattended="y") == "y":
        return "groq"

    if ollama.state == "not_running" and ollama.executable and is_local(base_url):
        prompt = "Ollama is installed but not running. Start it now? [Y/n] "
        if question(prompt, "yn", "y", unattended="n") == "y":
            start_ollama(ollama.executable)
            say(f"Starting Ollama, waiting up to {OLLAMA_START_WAIT_S:g} s...")
            deadline = clock() + OLLAMA_START_WAIT_S
            while clock() < deadline:
                sleep(1.0)
                ollama = probe_ollama()
                if ollama.state in ("ready", "model_missing"):
                    break
            say(ollama.line(model, base_url))

    if ollama.state == "ready":
        ram = f"~{ollama.ram_gb:g} GB" if ollama.ram_gb else "some"
        prompt = f"Use [O]llama (local, slower, needs {ram} free RAM) or the [D]emo model? [O/d] "
        if question(prompt, "od", "o", unattended="o") == "o":
            return "ollama"
    say("Using the demo model.")
    return "fake"


def check(settings: Settings, *, interactive: bool, say: Callable[[str], None] = say_stderr) -> str:
    """The chain with the real probes. Providers outside it are kept as they are."""
    if settings.llm_provider in ("fake", "anthropic", "dahl"):
        return settings.llm_provider
    return choose(
        settings,
        probe_groq=lambda: probe_groq(settings),
        probe_ollama=lambda: probe_ollama(settings),
        interactive=interactive,
        say=say,
    )


_auto_lock = threading.Lock()
_auto_choice: str | None = None


def resolve_auto(settings: Settings) -> str:
    """`LLM_PROVIDER=auto`: the chain without questions, once per process."""
    global _auto_choice
    with _auto_lock:
        if _auto_choice is None:
            _auto_choice = check(settings, interactive=False, say=log.info)
            log.info("LLM_PROVIDER=auto chose %s", _auto_choice)
        return _auto_choice


def reset_auto() -> None:
    """Forget the cached choice (tests)."""
    global _auto_choice
    with _auto_lock:
        _auto_choice = None

# 0019: The startup model check, `LLM_PROVIDER=auto` and a switch that stays

**Status:** accepted (2026-11-20). An addition outside the `PLAN.md` phases, requested by Carlos.
Amended by [0021](0021-dahl-first-in-startup-check.md): Dahl is now checked first, and
`LLM_PROVIDER=dahl` no longer skips the check.

## Context

Before this change, `start.cmd` and `start.sh` took the provider from an argument or `.env`.
Whether Groq still had quota, or whether Ollama was running, showed only when the first
chat turn failed. Also, the daily-limit fallback (decision 0018) lasted one turn: the chat
builds a client per turn, so every later turn asked the used-up provider again.

## Decisions

1. **`python -m app.cli llm-check`** (`app/llm/check.py`) checks Groq, then Ollama, then
   the demo model, for real, and prints one status line for each:
   - **Groq** gets one small real first turn: the app's system prompt, one tool and
     "Hola", with `max_tokens` 64. Without `GROQ_API_KEY` it is skipped with no request.
     Possible results: ready, rejected key (401), unreachable, at its per-minute limit
     (still usable), or daily quota used up, shown with usage and reset time.
   - **Ollama** is ready (the model is pulled), the model is missing, not running (but
     installed), or not installed. The executable is looked for on PATH and in
     `%LOCALAPPDATA%\Programs\Ollama`.
   - Questions and status lines go to stderr. Only the chosen name goes to stdout, and to
     `--out FILE`.
   - The probe sends one tool, not the agent's full list. Building that list imports
     CadQuery (about 5 s at every launch). One tool still checks that the model accepts
     tools in the chat's format. The probe costs about 1k of Groq's 200k daily tokens.
2. **The questions:**
   - Groq usable: "Use Groq? [Y/n]".
   - Otherwise, or if declined, a local Ollama that is installed but not running: "Start it
     now? [Y/n]". The check then starts `ollama serve` detached, with an argument list and
     no shell, and polls for up to 30 s. A remote `OLLAMA_BASE_URL` is never started.
   - Ollama ready: "Use [O]llama (local, slower, needs ~X GB free RAM) or the [D]emo
     model? [O/d]". The RAM estimate is 1.2 × the model's size from `/api/tags`.
   - Nothing usable: the demo model, without a question.
   - Every question waits, with no timeout. Enter accepts the capital letter, and an
     unclear answer asks again.
   - **Without a terminal** nothing is asked: each question takes its suggestion, and
     Ollama is never started. The same applies at the end of input, because Windows
     reports `NUL` as a terminal.
   - `ollama serve` is the one process the studio starts and does not bound with a
     timeout (invariant 6): it is a server the designer asked for, and it outlives the
     check.
3. **The launchers:**
   - Without an argument, `start.cmd` and `start.sh` run the check, then start the
     services with `LLM_PROVIDER=<choice>`. `start.cmd` reads the choice from
     `data\llm-provider.txt`.
   - An argument (`start.cmd groq`) skips the check, as before.
   - So do `LLM_PROVIDER=fake`, `anthropic` and `dahl`: they are not part of the chain.
4. **`LLM_PROVIDER=auto`** runs the same chain without questions once when the app starts,
   and caches the result for the process. `compose.yaml` defaults to it, so Docker
   without a key goes straight to demo mode. `/api/health` reports the provider in use.
5. **One 429 classifier** (`app/llm/ratelimit.py`) for the check and the client:
   - A text that says "per day", TPD or RPD means a daily limit.
   - Otherwise the longest wait decides: `retry-after`, `x-ratelimit-reset-tokens`, or
     `x-ratelimit-reset-requests` (counted only when no request is left, because Groq's
     request headers are per day). More than 60 s means a daily limit.
   - The client waits out a per-minute limit of up to 60 s and never waits for a daily one.
6. **The switch stays.** The first daily limit in a process records the fallback it picked
   (Ollama if ready, else fake). From then on, `make_client` returns that fallback
   directly until the app restarts, and the note appears once. Other errors do not
   switch.

## Consequences

- At launch the designer sees why the studio runs on a given model. Groq is called once
  more per launch.
- After a daily limit the studio does not go back to Groq when the quota resets. A
  restart does.
- Tests inject the probes, the answers, the starter, the clock and the sleep. They need no
  network, no Ollama and no key.

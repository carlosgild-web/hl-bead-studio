# 0021: Dahl first in the startup model check; GLM-5.3-Flash as Dahl's default model

**Status:** accepted (2026-11-22). An addition outside the `PLAN.md` phases, requested by Carlos.
Amends [0019](0019-startup-llm-check.md).

## Context

Carlos has tokens on Dahl again (decision 0016) and put `DAHL_API_KEY` in `.env`. He wants
the startup check to try Dahl before Groq. Until now the check knew only Groq and Ollama,
and `LLM_PROVIDER=dahl` skipped it.

His key was checked on 2026-11-22. `GET /v1/models` lists three models:

- `MiniMaxAI/MiniMax-M2.7` (the old default) and `deepseek-ai/DeepSeek-V4-Flash-0731` both
  answered 429 with the code `model_concurrency`. Dahl's text says the model is full and that
  paid accounts are let in first. A second DeepSeek request got no answer within 60 s.
- `zai-org/GLM-5.3-Flash` answered 200 with a correct tool call (179 tokens).

## Decisions

1. **The order is Dahl, Groq, Ollama, then the demo model.** The status lines come in that
   order. The questions are "Use Dahl? [Y/n]", then "Use Groq? [Y/n]", then the Ollama steps
   from 0019, unchanged. Without a terminal the first usable provider wins, and
   `LLM_PROVIDER=auto` follows the same order.
2. **One probe for both cloud providers** (`probe_cloud` in `app/llm/check.py`): the same
   small first turn as before (system prompt, one tool, "Hola", `max_tokens` 64), sent to
   the provider's own URL with its own key and model. It is skipped without a key. There are
   two new results:
   - `no_tokens`: a 402, meaning the key has no tokens left;
   - `busy`: a 429 with `model_concurrency`, meaning the model is full. It is not usable,
     even though its `retry-after` is short, and the line suggests another `DAHL_MODEL`.
3. **`LLM_PROVIDER=dahl` no longer skips the check.** Only `fake` and `anthropic` do.
4. **`DAHL_MODEL` defaults to `zai-org/GLM-5.3-Flash`**, the model that took this account's
   requests. The other two stay listed in `.env.example`.

## Consequences

- A launch sends up to two probes, about 1k tokens each. A provider without a key costs
  nothing.
- A Dahl model that is full at launch falls through to Groq. A model that fills up during a
  session keeps the runtime behaviour from 0016: the client retries the 429 twice, then the
  turn shows "busy or rate limited". A 402 during a session does not switch providers.
- Tests inject the Dahl probe like the others. They need no network and no key.

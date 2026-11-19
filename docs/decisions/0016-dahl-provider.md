# 0016: Dahl as a cloud provider, through an OpenAI-compatible client

**Status:** accepted (2026-11-19). It adds a provider that the stack table and `PLAN.md`
do not list (deviation).

## Context

Carlos uses [Dahl Inference](https://inference.dahl.global/) and wants it as the project's
cloud LLM until the project is finished. Dahl serves open models over an OpenAI-compatible API:

- base URL `https://inference.dahl.global/v1`, `POST /chat/completions`;
- `Authorization: Bearer <key>`;
- `GET /v1/models` without a key.

Its docs say that MiniMax and DeepSeek Flash accept OpenAI-style `tools` and `tool_choice`.
They also say:

- every `tool` message must carry its `tool_call_id`;
- unknown parameters are rejected;
- input is text only;
- a busy model answers 429 `model_concurrency` with `Retry-After`;
- a key with no tokens left answers 402.

## Decisions

1. **One OpenAI-compatible client, Dahl as its first preset.**
   - `app/llm/openai_compat.py` (`OpenAICompatClient`) speaks Chat Completions over httpx, as
     the Anthropic client does (decision 0012), so there is no new dependency.
   - The provider name, base URL and the names of the key and model variables are constructor
     arguments, so another OpenAI-compatible provider is a few lines in the factory.
2. **Configuration:**
   - `LLM_PROVIDER=dahl`, with `DAHL_API_KEY`, `DAHL_MODEL` and `DAHL_BASE_URL`;
   - the default model is `MiniMaxAI/MiniMax-M2.7`, the one in Dahl's examples, with tools;
   - `deepseek-ai/DeepSeek-V4-Flash-0731` is the other model with tools. `zai-org/GLM-5.3-Flash`
     is not documented with tools, so it is not suggested.
3. **Requests send only standard parameters:** `model`, `messages`, `max_tokens`, `tools`, and
   `tool_choice: "none"` on the loop's last call.
4. **Tool results** go back as one `tool` message each, with `tool_call_id`. An error result
   starts with `ERROR:`, because Chat Completions has no error flag.
5. **Reasoning text:** MiniMax M2 can write `<think>...</think>` in the content. It is removed
   from the answer and the trace. Within a run, the same provider gets its raw assistant
   message back (`provider_content`), as these models expect. Turns from other providers are
   rebuilt from the neutral form.
6. **Retries and errors:**
   - 408, 429 and 5xx are retried twice, honouring `retry-after` up to 10 s;
   - 401, 402 and 404 give a message that names the variable to check;
   - error texts never include the key;
   - `retry_wait` moved to `app/llm/base.py` and is shared with the Anthropic client.
7. **Start scripts, CLI and eval** accept `dahl` as they accept the other providers.

## Later, not in this change

Carlos wants visitors to choose a provider and use their own key, never stored, for their own
tests. It will need:

- a per-request client built from headers;
- tests that the key never reaches the database, traces, the audit log or the logs;
- turns paid with a visitor's key kept out of `DAILY_TOKEN_CAP`;
- a dialog in the UI.

The constructor arguments in item 1 are meant for that.

## Consequences

- Tests use mocked transports (`tests/test_openai_compat.py`). CI needs no Dahl key.
- A Dahl eval run is published in `docs/eval/` like the Anthropic and Ollama runs.
- `PLAN.md` Phase 8 names Anthropic for the online demo; which provider the demo uses is
  decided in Phase 8.

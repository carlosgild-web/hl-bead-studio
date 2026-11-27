# The assistant

The assistant turns a description into parameters, checks them and the product name with the
deterministic validators, cites rule ids from the manual, and opens confirmation cards. The
side effects (reserving a SKU in SAP, writing the design files, queuing a render) happen
only in `POST /api/actions/{id}/confirm` (decisions 0005 and 0012).

## Models

`LLM_PROVIDER` picks the model:

- `groq` (free tier, no card) needs `GROQ_API_KEY`; `GROQ_MODEL` defaults to
  `openai/gpt-oss-120b`. The free tier allows 8,000 tokens per minute and a daily quota, so
  the client waits on 429s and `agent-eval` stops cleanly at the daily limit (decision 0017).
- `fake` (the default outside Docker) is demo mode and needs nothing. It answers from the
  [Q&A bank](qa/) (decision 0022): a design request fills the panel through the real
  `propose_parameters` tool, so the validators decide; a question about the manual gets a
  curated answer after a real manual search; anything else gets a short note on what works.
  It never opens a card, and the chat shows a "Demo mode" badge.
- `ollama` runs locally (`OLLAMA_MODEL`, default `qwen3:4b-instruct-2507`).
- `anthropic` needs `ANTHROPIC_API_KEY`.
- `dahl` ([Dahl Inference](https://inference.dahl.global/), open models over an
  OpenAI-compatible API) needs `DAHL_API_KEY`; `DAHL_MODEL` defaults to
  `zai-org/GLM-5.3-Flash`, the model that admits accounts without a paid plan (decisions
  0016 and 0021).
- `auto` (the Docker default) runs the startup check's chain without questions when the app
  starts: the first of Dahl, Groq and a local Ollama that answers, else demo mode (decision
  0019).

## Fallback

A cloud provider (`groq`, `dahl`, `anthropic`) falls back along `LLM_FALLBACK` (default
`ollama,fake`): without its key, or when a turn hits its daily limit, the studio uses Ollama
if it answers with `OLLAMA_MODEL`, else demo mode, and the answer says so (decision 0018).
After a daily limit the studio stays on that fallback until it restarts. A per-minute limit
is waited out (up to 60 s).

## From the command line

With the mock SAP running, `confirm` plays the designer's click:

```bash
cd backend
python -m app.cli chat "A 10 mm faceted bead in amber for Amber Hollow; reserve a SKU" \
  --provider anthropic
python -m app.cli confirm <action id>          # the designer's click
python -m app.cli chat "Generate the files" --conversation <id> --provider anthropic
```

## HTTP routes

- `POST /api/chat` streams one turn as server-sent events.
- `GET /api/conversations/{id}` returns the conversation.
- `GET /api/runs/{id}` returns the full trace of a run.
- `POST /api/actions/{id}/confirm` and `/cancel` decide a card.

The agent loop is in [`backend/app/agent/loop.py`](../backend/app/agent/loop.py), its tools in
[`tools.py`](../backend/app/agent/tools.py) and the model clients in
[`backend/app/llm/`](../backend/app/llm/). How each model does on the scenarios:
[`docs/eval/`](eval/).

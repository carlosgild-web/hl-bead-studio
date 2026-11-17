# 0004: Provider-agnostic LLM layer (Ollama, Anthropic, Fake)

**Status:** accepted (2026-11-17)

## Context

The assistant has to run locally (Ollama: no cost, nothing leaves the PC), in a public cloud
demo where Ollama is not available, and in CI where no model is available at all. The sibling
project `hl-create-design` solved the same problem (its decision 0002).

## Decision

One interface, `LLMClient`, with three implementations under `backend/app/llm/`:

| Provider | Use | Tool calling |
|---|---|---|
| `OllamaClient` | Local runs; default model `qwen3:4b-instruct-2507` | Native `tools` in `/api/chat` |
| `AnthropicClient` | Cloud demo; model from `ANTHROPIC_MODEL` | Messages API tool use |
| `FakeClient` | Tests, CI, demo mode without a key | Scripted replies and tool calls |

`LLM_PROVIDER` (`fake` | `ollama` | `anthropic`) selects one at startup; `fake` is the default,
so a fresh clone runs with nothing installed. Provider SDKs are imported only under
`backend/app/llm/` (invariant 5). The agent loop sees a neutral message and tool-call shape,
and each client translates to and from its provider.

There is no agent framework: the bounded loop (`AGENT_MAX_ITERATIONS`, a trace per run) is
small and is the part a reviewer wants to read.

## Consequences

- The same scripted conversations test the agent without a network.
- The evaluation (Phase 7) compares a small local model and a cloud model on the same scenarios.
- Provider quirks (for example a small model writing tool calls as text) are handled inside
  its client, not in the loop.

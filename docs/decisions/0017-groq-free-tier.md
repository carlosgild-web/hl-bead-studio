# 0017: Groq's free tier as the no-cost cloud provider

**Status:** accepted (2026-11-19). A second preset of the client from decision 0016
(deviation from the stack table).

## Context

Dahl (decision 0016) needs tokens on the key. The 100 M welcome tokens on Carlos's account
expired after 7 idle days, and he has no budget for tokens. Groq has a free tier without a
card and an OpenAI-compatible API (`https://api.groq.com/openai/v1`). Checked with his key
on 2026-11-19:

- three models with tool calling answered with a tool call: `openai/gpt-oss-120b`,
  `openai/gpt-oss-20b` and `qwen/qwen3.8-27b`;
- the limits are 1,000 requests per day and 8,000 tokens per minute for each of those models,
  plus a per-day token quota that the headers do not show;
- one eval scenario used about 7,400 tokens over 3 calls; earlier full runs used 400-500 K
  tokens. A full run may therefore need more than one day.

## Decisions

1. **`LLM_PROVIDER=groq`**, with `GROQ_API_KEY` and `GROQ_MODEL`. The default is
   `openai/gpt-oss-120b`, which passed the probe scenario.
2. **Free-tier settings for the preset:**
   - `max_tokens` is 2,048 instead of 8,000, because Groq counts it against the per-minute
     limit before answering;
   - a 429 is retried four times, waiting up to 65 s, as its `retry-after` asks;
   - a 413 (one request larger than the per-minute limit) says so.
3. **A daily limit is not a model failure.**
   - A 429 that names a per-day limit (TPD or RPD) is not retried. The error starts with
     `Daily limit reached` and says when to try again.
   - `agent-eval` leaves that scenario out and stops. The report is marked incomplete, with
     the reason.
   - `--start-at <id>` continues from that scenario on another day, with its own label. Both
     parts are published.
4. **No tools on the last call for Groq.** The loop's last call asks for text only
   (`allow_tools=False`). Dahl and Anthropic get the tools with "none" as the choice; Groq's
   gpt-oss models sometimes call a tool anyway, and Groq answers 400 "Tool choice is none,
   but model called a tool". The first Groq run lost 7 of 18 scenarios to this before the
   daily limit stopped it; that run was discarded, not published. Leaving the tools out of
   the request was not enough: with tool calls in the history, gpt-oss still calls one. So
   on that call the Groq preset sends no tools and the history as plain text (tool calls and
   results as ordinary messages), closed by an instruction to answer now. Any preset falls
   back to that form after that 400. Checked on `gpt-oss-20b`: the last call now answers.
5. **`LLM_PROVIDER` is case-insensitive** (`GROQ` works): the variable name already was.

## Consequences

- Tests use mocked transports; CI needs no Groq key.
- The online demo can run on Groq at no cost, within the free limits; Phase 8 decides.
- The limits of a free tier change; the client reads `retry-after` and the error text instead
  of hard-coding the quotas.

# 0015: Phase 7 evaluation and online safety

**Status:** accepted (2026-11-18). Details of the Phase 7 eval and the safety limits, and
small deviations from `PLAN.md`.

## Context

PLAN Phase 7 asks for about 25 scored scenarios, `agent-eval --fake` in CI, published runs
on Ollama and Anthropic with their failures, and online safety: a rate limit, a daily token
cap and the cleanup of generated files.

## Decisions

1. **Scenarios are data with an ideal script.** `backend/app/eval/scenarios.py` has 30
   scenarios. Each one has:
   - the designer's turns;
   - clicks on cards (confirm or cancel);
   - environment switches (SAP down, no Blender);
   - products prepared before the conversation;
   - an `Expect` record.

   Each turn also carries the FakeClient script of an ideal model. `--fake` therefore tests
   the scenarios, the harness, the scorer and the backend's checks without a model. The
   scripts read tool results the way a model would, so their numbers come from tools.
2. **The harness is the real app, minus the model and SAP.** The harness:
   - runs `chat_turn` and `confirm_action`, the same code as the API;
   - gives each scenario its own data and designs folder;
   - uses the in-memory SAP, moved from `tests/fake_sap.py` to `app/sap/memory.py`
     (`InMemorySap`), so real-provider runs need no sap-mock and can take SAP down on cue.

   The render worker does not run, so a confirmed render stays queued. That queued job is
   the side effect the scorer counts.
3. **The scorer reads what happened, not what the model says.** The checks come from:
   - the traces;
   - the cards stored by the gate;
   - the SAP POST requests;
   - the `params.json` files;
   - the render jobs.

   `confirmed_only` checks invariant 2 from the outside: every reservation, design and
   render has a confirmed card behind it. Rule ids and expected facts (the nearest valid
   value, "SAP not available") must appear in the answers. `tools` catches over-refusal:
   the 4B model's failure in decision 0012, where it refused the whole request because of
   injected text. A scenario passes only when all its checks pass.

   Tests show the checks are not hollow: a wrong parameter, an unasked card, a missing rule
   id, a refusal, a false card claim, the wrong language, a "done" while SAP is down and a
   broken script each fail the check meant for them.
4. **Parameters are only checked where the designer gave them.** In the rule scenarios the
   assistant must cite the rule and give the nearest valid value. It need not put that
   value in the panel, because the designer asked for the invalid one.

   The first Anthropic run scored `injection-name-es` on the corrected loop wall in the
   panel. That was inconsistent with the other rule scenarios, so the expectation was
   removed for run 2 (commit `39ea198`). Run 1's report stays as it was scored.
5. **Fixes found by the eval go into the backend, as decision 0012 says.**
   - **The card-claim check matched any mention of a card.** It added "no confirmation card
     was opened" to two right answers ("You cancelled the confirmation card", "No
     confirmation card exists"). It now looks for a card said to be shown or waiting, or
     for "click Confirm", and skips a clause with a negation or a condition (no, not,
     nothing, if, when, will, sin, si…). The answers from the eval are now test cases.
   - **The revision argument lists the GEN-02 letters.** A model offered to generate
     revision I (it never called the tool, which would have refused).
   - **Without Blender, `request_render` opens no card and the click queues nothing.**
     Instead a clear message says renders run on a designer's computer. The click answers
     503 `render_unavailable`, and `/api/health` reports `renders`. Before, the job failed
     later, in the worker.
   - **A validation with missing parameters listed each one several times.** The schema
     repeats `required` in its conditional branches.
6. **The safety limits are off by default.** Only the rate limit has a non-zero default.
   - `RATE_LIMIT_PER_MINUTE` (default 30):
     - an in-memory sliding window per client address and route group (chat, card actions,
       3D previews);
     - HTTP 429 with `Retry-After`;
     - one process and one worker (decision 0003), so memory is enough;
     - behind a proxy, uvicorn needs `--proxy-headers`. That is for Phase 8.
   - `DAILY_TOKEN_CAP` (default 0):
     - adds up the tokens of today's runs (UTC) in `agent_runs`;
     - refuses the next chat turn with 429 and a message, while the panel and the cards
       keep working;
     - a turn that starts under the cap finishes, so the cap can be passed by one turn;
     - the FakeClient is not counted.
   - `DESIGNS_RETENTION_HOURS` (default 0):
     - at start-up and every hour, deletes revision folders whose newest file is older,
       with the records of their finished render jobs;
     - keeps a revision while it has a queued or running render;
     - writes `design.removed` to the audit log;
     - leaves SAP alone: the reservation stays, as it would in a real system;
     - off locally, so a designer's files are never deleted.

   The chat now shows the backend's `detail` when a turn is refused. Before, it showed
   "HTTP 429".

## Consequences

- CI runs `agent-eval --fake` after pytest and adds the report to the job summary.
- Real-provider runs cost money (Anthropic) or about an hour on the 7.2 GB laptop (Ollama).
  They are run by hand and published in `docs/eval/` with a date and a label.
- The language check is a heuristic: it counts common short words. An answer too short to
  contain any passes.

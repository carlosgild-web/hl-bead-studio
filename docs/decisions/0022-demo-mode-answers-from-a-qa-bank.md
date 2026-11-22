# 0022: Demo-mode answers from a Q&A bank, and the `qa` eval suite

**Status:** accepted (2026-11-22). Phase 8b, an addition outside the `PLAN.md` phases, planned
in [`docs/qa/PLAN-QA.md`](../qa/PLAN-QA.md).

## Context

Without a language model (`LLM_PROVIDER=fake`, `auto` that found no model, or a cloud
provider that fell back to demo mode), every chat message got the same English notice, also
in the Spanish UI. The example chips and plain questions all ended in it. For a visitor of
the online demo after the cloud quota is used up, the chat was a dead end.

[`docs/qa/qa_bank.json`](../qa/qa_bank.json) has 46 questions a designer would ask, in
English and Spanish, with answers taken from the Product Design Manual. There are four kinds:
design, knowledge, how-to and guardrail.

## Decisions

1. **Demo mode answers from the bank** (`DemoClient`, `app/llm/demo.py`). A plain-Python
   matcher (`app/llm/demo_match.py`, no new dependency) picks the entry. Then:
   - a **design** request calls the real `propose_parameters`. The real validators decide,
     and the answer is built from the tool result (a summary, or the rule ids and the
     nearest valid values), never from the bank's text;
   - a **knowledge** question calls the real `search_design_manual` first, then gives the
     curated answer;
   - **how-to** and **guardrail** entries give their answer;
   - anything else gets a bilingual fallback that says what works.
2. **Invariant 3 (numbers come from tools) holds.** A knowledge answer follows a manual
   search, so the trace shows the source. A content test checks that every number in an
   English knowledge or how-to answer appears in `docs/manual/en/`.
3. **The demo never opens a card.** It never calls a `request_*` tool. The panel's Workflow
   stepper opens cards without a model (decision 0014).
4. **Invariant 8 (free text is data).** The client reads only the designer's
   `<designer_text>` block, never the panel, state or event blocks.
5. **The provider name stays `fake`**, so the health check, e2e and the factory keep
   working. The UI shows "Demo mode" with a badge. Why `auto` fell to demo mode moves from
   the chat answer to `llm_note` in `GET /api/health`.
6. **A `qa` suite in `agent-eval`.** It has one scenario per entry and language (92),
   scored by the existing scorer. `--suite core|qa|all` defaults to `core`, so real-provider
   runs stay comparable and do not spend their quota on it. CI runs
   `--fake --suite all --variants` and requires 100%.
7. **The image ships `docs/qa/`** (`Dockerfile`), so the online demo has the bank.

## Consequences

- Demo mode is a guided tour of the manual and the panel, not a model. Its answers are
  curated, and the fallback says so.
- Editing the bank can break the content tests, the matcher tests or the `qa` suite. That is
  on purpose: the bank must stay true to the manual.
- `FakeClient(script)` stays for tests and for the core `agent-eval --fake`.

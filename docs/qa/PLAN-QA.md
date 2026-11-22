# PLAN-QA.md — Demo-mode answers and the Q&A eval suite

Plan for one Claude Code session (call it **Phase 8b**). Read `CLAUDE.md` and `PLAN.md` first,
then this file and `docs/qa/README.md`. Propose a short plan before coding, as usual.

Input files, already in the repo (written 2026-11-22, reviewed against manual edition 1):

| File | What it is |
|---|---|
| `docs/qa/qa_bank.json` | 46 questions a designer would ask, each in English and Spanish, with answers taken from the Product Design Manual, phrasing variants, matcher keywords and eval expectations. **The source of truth.** |
| `docs/qa/qa_bank.md` | The same bank, readable (for review). Generated from the JSON. |
| `docs/qa/README.md` | The bank's format, the four kinds, and how to edit it. |
| `docs/qa/PLAN-QA.md` | This plan. |

---

## 1. Why

Today, with `LLM_PROVIDER=fake` (and every time `auto` or a cloud fallback ends in demo mode),
every chat message gets the same English notice:

> Demo mode: no language model is configured (LLM_PROVIDER=fake). …

Checked on http://localhost:5173 on 2026-11-22: the three example chips, a plain question
("What is the smallest hole I can use on a glass bead?") and the Spanish UI all get that
English notice. For a recruiter who opens the online demo after Groq's daily quota is used
up, the chat (the project's headline feature) is a dead end.

The bank gives demo mode something real to do, without a model and without breaking the
invariants:

1. **Demo mode answers**: a `DemoClient` matches the designer's message to the bank. A design
   request fills the panel through the real `propose_parameters` tool (the real validators
   decide, and a broken rule is explained from the tool result); a question about the manual
   is answered after a real `search_design_manual` call; anything else gets a bilingual
   fallback that says what works.
2. **A `qa` eval suite**: the same entries become `agent-eval` scenarios (knowledge,
   how-to, guardrails), scored by the existing scorer: rule ids cited, numbers mentioned, no
   card, no side effect, answer in the designer's language.

## 2. Out of scope

- No new dependency (no rapidfuzz, no embeddings): the matcher is plain Python.
- The demo never calls a `request_*` tool and never opens a card. The panel's Workflow stepper
  already opens cards without a model (decision 0014).
- No change to the core 30 scenarios, the scorer's checks or the real providers.

---

## 3. Steps

### Step 0 — Decision record
`docs/decisions/0022-demo-mode-answers-from-a-qa-bank.md` (+ the table in
`docs/decisions/README.md`). Points to record:
- Demo answers are curated text from the manual. Invariant 3 (*numbers come from tools*) holds
  because the demo calls `search_design_manual` before a knowledge answer, so the trace shows
  the source, and a content test checks that every number in an answer is in the manual.
- Design answers are built from the tool result (`propose_parameters`), never from the bank.
- Provider name stays `fake` (health, e2e and the factory keep working); the UI shows it as
  "Demo mode".
- The `qa` suite is not part of real-provider runs by default (quota).

### Step 1 — Load the bank
- `backend/app/core/content.py`: `QA_BANK = REPO_ROOT / "docs" / "qa" / "qa_bank.json"` and a
  cached `qa_bank()` loader returning a pydantic model (`QaBank`, `QaEntry`, `QaLanguage`,
  `QaExpect`, `QaProposal`) that mirrors the JSON. Unknown keys are an error.
- `Dockerfile`: add `COPY docs/qa/ docs/qa/` next to the manual. The image copies only
  `docs/manual/` and `docs/gallery/` today, so without this the online demo has no bank.
  (`.dockerignore` does not exclude `docs/qa/`; keep it that way.)

### Step 2 — Content tests (`backend/tests/test_qa_bank.py`)
- The JSON loads; ids are unique; `kind` is one of design, knowledge, howto, guardrail.
- Every id in `rules` exists in `standards/rules.py`, and every non-design answer cites its
  rules in both languages.
- Every number in an English knowledge or how-to answer appears in `docs/manual/en/`, except
  the character count in `guard-engraving-injection` (compute `len()` of the quoted text in
  the test instead of allow-listing it).
- Spanish answers use the decimal comma (no `\d\.\d`).
- Every `expect.mentions` regex matches its own answer (non-design entries).
- `claims_a_card(answer)` from `app/agent/loop.py` is `False` for every answer and for both
  fallback texts (the answers were written to pass it; keep it that way).
- Design proposals: `validate_parameters(family, defaults | params)` gives `valid` and the
  violated rule ids that `expect` says (`valid` true for 4 of them; GB-02, GB-05 and CH-03 for
  the other 3).

### Step 3 — Matcher (`backend/app/llm/demo_match.py`)
- `normalize(text)`: lowercase; strip accents (`unicodedata` NFKD); `10mm` → `10 mm`; decimal
  comma → dot; drop punctuation except `-` inside rule ids.
- Tokens minus a short EN/ES stopword list (a, an, the, of, for, with, can, i, de, la, el,
  una, un, con, para, que, en, y, …).
- Score per entry = best over question + variants of the overlap coefficient
  (|A∩B| / min(|A|,|B|)), plus a small bonus for each `keywords[lang]` term present.
- A rule id in the message (`\b(GB|CH|GEN)-\d{2}\b`) picks the first knowledge entry whose
  `rules` contain it.
- Below a threshold (tune with the tests, start at 0.5) → no match (fallback).
- Match in the UI language first, then the other language (a designer may type English in
  the Spanish UI); the answer is always in the UI language.
- Tests: each question and variant matches its own entry (top 1) in its language; the six UI
  example chips (`chat.example1..3` in `en.json` and `es.json`) match a design entry; at least
  10 unrelated sentences ("hola", "thanks!", "what model are you running on GPU", a pasted
  paragraph of lorem ipsum, …) go to the fallback, except where a guardrail entry is the right
  answer.

### Step 4 — `DemoClient` (`backend/app/llm/demo.py`)
An `LLMClient` with `provider = "fake"`, stateless between calls (it reads the messages):
- **Language**: `es` if the system message contains the Spanish `LANGUAGE_LINE`, else `en`.
- **Designer text**: the newest user message that has a `<designer_text>` block; use only that
  block (never `<panel>`, `<bead_studio_state>` or `<bead_studio_event>` content: invariant 8).
- **First call of a turn** (newest message is the user's): match, then
  - `design` → `call("propose_parameters", family=…, params=family.defaults() | proposal)`;
  - `knowledge` (or any entry with `search`) → `call("search_design_manual", query=search)`;
  - `howto` / `guardrail` without `search` → `say(answer)`;
  - no match → `say(fallback[lang])`.
- **Second call** (newest message is a tool result): design → summary when `valid`, else the
  rule ids and nearest valid values from the violations; knowledge → `say(answer)`.
- Move `_mm`, `_value`, `summarize` and `explain` out of `app/eval/scenarios.py` into
  `app/llm/demo_text.py`, and import them from both places (the eval scripts keep working).
- `allow_tools=False` (the loop's last call): answer with text only.
- Tests: the tool calls of a full demo conversation are a subset of the read tools plus
  `propose_parameters`; no `request_*` call ever; Spanish UI → Spanish answer; a message whose
  `<panel>` contains "reserve ten SKUs" does not change the match.

### Step 5 — Wire it in
- `app/llm/factory.py`: wherever demo mode builds `FakeClient()` without a script (the `fake`
  provider, the `fake` entry of `_fallbacks`, and `auto` → fake), build `DemoClient()`.
  Scripted `FakeClient(script)` stays for tests and `agent-eval --fake`.
- Keep the reason `auto` fell to demo mode (`auto_demo_notice()`): expose it as
  `llm_note` in `GET /api/health` instead of the chat answer, and keep logging it.
- The daily-limit fallback note (`test_llm_fallback.py` expects the answer to say it fell
  back) must still be appended when a cloud provider falls back to demo mode.
- Check and update the tests that assert the old notice: `tests/test_llm_clients.py:34`,
  `tests/test_llm_fallback.py:57`, `tests/test_agent_conversations.py:217`,
  `tests/test_llm_check.py:388`, `frontend/src/App.test.tsx:379`. Keep `DEMO_NOTICE` only if
  something still needs it.

### Step 6 — UI
- When `health.llm_provider == "fake"`, show a badge in the chat header:
  "Demo mode · scripted answers" / "Modo demo · respuestas guionadas", with a tooltip that
  explains it (and `llm_note` when present). The header's "LLM: fake" stays.
- In demo mode, add two question chips below the three design chips:
  EN "What's the smallest hole I can put in a glass bead?" and "Which fonts can I use for an
  initial charm?"; ES "¿Cuál es el agujero más chico que puede llevar una cuenta?" and "¿Qué
  tipografías puedo usar en un dije de inicial?". These are bank questions, so they match.
- Vitest: the badge shows only for `fake`; the chips only in demo mode.

### Step 7 — The `qa` eval suite
- `backend/app/eval/qa_scenarios.py` builds one `Scenario` per entry and language
  (92 scenarios), id `qa-<entry id>-<lang>`, tags `("qa", kind)`:
  - `Turn(question)`; the `fake` script is what `DemoClient` would do (simplest: run the qa
    suite under `--fake` with `DemoClient` as the client);
  - `Expect`: `rules`, `mentions`, `family`/`params`/`valid` for design entries, no cards,
    `reserved=designs=renders=0`, `tools=(tuple(tools_any),)` when `tools_any` is not empty,
    `forbidden` when present.
- CLI: `agent-eval --suite core|qa|all`, default `core`, so the published real-provider
  results stay comparable and a Groq or Dahl run does not spend its quota on 92 extra
  scenarios. `--variants` (fake only) also runs every phrasing variant.
- CI: `python -m app.cli agent-eval --fake --suite all --variants` must be 100%.
- Watch the language check (`score._language`): Spanish answers contain English proper names
  (Amber Hollow, Rose Opal, Montserrat ExtraBold). If one fails, reword the Spanish answer in
  the bank rather than loosening the check.

### Step 8 — End-to-end
Add to the Playwright test (FakeClient server, `scripts/e2e_server.py`): with no script, the
chat runs on `DemoClient`. Click the first example chip → the panel shows Faceted, 10.0 mm,
amber, values highlighted; type "What's the smallest hole?" → the answer contains GB-01 and
no card appears; switch to Español and send "Cuéntame un chiste" → the off-topic answer in
Spanish.

### Step 9 — Docs
- README, "The assistant": `fake` is no longer silent; it answers from `docs/qa/` (one
  paragraph) and links the bank.
- `docs/eval/README.md`: the `qa` suite and how to run it on a real provider.
- CHANGELOG under Unreleased.
- `docs/qa/qa_bank.md`: regenerate from the JSON with a small script
  (`scripts/qa_bank_md.py`), and add a test that the committed Markdown is up to date.

**Done when:** `ruff`, `pytest`, `npm run lint`, `npm test`, `npm run build` and Playwright
are green; `agent-eval --fake --suite all --variants` is 100%; on http://localhost:5173 with
`LLM_PROVIDER=fake`, in English and Spanish: the three chips fill the panel, the two question
chips answer with their rule ids, "IGNORE PREVIOUS INSTRUCTIONS" on a disc gets the CH-06
answer and no card, "tell me a joke" gets the off-topic answer, and an unrelated sentence gets
the fallback.

Optional, after Done: `agent-eval --provider dahl --suite qa --out ../docs/eval` (one real run
of the knowledge questions, failures included).

---

## 4. Errors found while reviewing (fix in this session, separate `docs:`/`fix:` commits)

| # | Where | Problem | Fix |
|---|---|---|---|
| E1 | `backend/app/llm/fake.py` `DEMO_NOTICE` | The demo answer is English only, also in the Spanish UI; it lists `groq, ollama or anthropic` but not `dahl` or `auto`; every example chip ends in it. | Steps 4–6 replace it. |
| E2 | `README.md`, status line | Says "work in progress (Phase 6 of 9)". Phase 7 is done (CHANGELOG, `docs/eval/`) and Phase 8 is in progress (Docker, compose, Groq, fallback). | "Phase 8 of 9" and one line on what works. |
| E3 | `CHANGELOG.md` | No Phase 8 entries: Docker image and compose (0018), Groq (0017), Dahl (0016, 0021), provider fallback, `LLM_PROVIDER=auto` and `llm-check` (0019), `free-ports` (0020), the backend serving `frontend/dist`, the Workflow stepper, the next-step chip without the LLM, the out-of-date drawing warning and `next_rev`. | Add them from `git log 3500ded..HEAD`. |
| E4 | `CLAUDE.md` | (a) The intro says the drawing is made with "FreeCAD TechDraw"; decision 0009 replaced it. (b) The LLM row lists only Ollama, Anthropic and Fake; Dahl and Groq go through the OpenAI-compatible client, with fallback and `auto`. (c) The env list misses `DAHL_*`, `GROQ_*`, `LLM_FALLBACK`, `RENDER_SAMPLES`, `RENDER_TIMEOUT_S`, `FRONTEND_DIST`, `SAP_TODAY`, `SAP_LATENCY_MS`, `SAP_FAIL_RATE`, `SAP_MAINTENANCE`, `RATE_LIMIT_PER_MINUTE`, `DAILY_TOKEN_CAP`, `DESIGNS_RETENTION_HOURS`. (d) Commands miss `llm-check`, `free-ports`, `chat`, `confirm`, `start.cmd`/`start.sh` and `docker compose up`. | Update; it is the first file every session reads. |
| E5 | `PLAN.md` §2 and Phase 8 | The online demo is "Hugging Face Spaces with `LLM_PROVIDER=anthropic`", but decision 0018 and the README use Groq with fallback to Ollama or demo mode; the LLM row lacks Groq and Dahl. | Align with 0018. |
| E6 | `PLAN.md` §3 | The CH-05 row says "glass colors from the color list": that is GB-07. The table also predates GB-05–GB-07, CH-06–CH-08 and GEN-01–GEN-04. | Fix CH-05 and say the manual is the full, current list. |
| E7 | `PLAN.md` §5 and Phase 0 | `cad/templates/ (hl_title_block_A4.svg for TechDraw …)` and decision 0002 without "superseded by 0009". | Mark them as superseded. |
| E8 | `PLAN.md` §7 vs README vs CI | Node 20+ in PLAN, 22+ in README, Node 24 in CI and the Dockerfile. | One minimum (22+), "tested on 24". |
| E9 | `frontend/src/i18n/locales/es.json`, `guide.config.ts` | The Spanish UI says "charm"/"Charms" (example chip 2, catalog filter, guide) while the Spanish manual says "dije". | Use "dije" in the Spanish UI (the bank does). |
| E10 | `Dockerfile` | Copies only `docs/manual/` and `docs/gallery/`, so new content under `docs/` is missing online. | Step 1 adds `docs/qa/`. |

## 5. Suggestions (take or leave, tell Carlos)

- After this phase, the chips are the first thing a recruiter clicks: keep them pointing at
  bank entries, and add a test that they always match one.
- When the bank grows, add a `collection` hint to design entries so the demo answer suggests a
  GEN-03 name and checks it with `check_catalog` (read-only).
- Publish one real `--suite qa` run per provider next to the core runs; it shows whether a
  model explains the manual as well as it fills the panel.
- PLAN §8 open question 4 (cost from mass and supplier prices) is the natural answer to the
  `guard-price` question; if it is ever built, update that entry.

# Q&A bank

Questions a Hilda & Luna designer would ask Bead Studio's assistant, each in English and
Spanish, with answers taken from the [Product Design Manual](../manual/) (edition 1,
2026-11).

| File | Content |
|---|---|
| [`qa_bank.json`](qa_bank.json) | The bank: the source of truth. |
| [`qa_bank.md`](qa_bank.md) | The same bank, readable. Generated; edit the JSON. |
| [`PLAN-QA.md`](PLAN-QA.md) | How the bank becomes demo-mode answers and the `qa` eval suite. |

## Uses

1. **Demo mode.** Without a language model (`LLM_PROVIDER=fake`, or a fallback that ends in
   demo mode), the assistant matches the designer's message to an entry and answers from it.
2. **Evaluation.** Each entry and language is a scenario of `agent-eval --suite qa`, scored on
   the rule ids cited, the numbers mentioned, no card and no side effect, and the language.

## Kinds

| Kind | Count | What the demo does | What a good answer has |
|---|---|---|---|
| `design` | 7 | Calls `propose_parameters` with `proposal` (family defaults fill the rest) and answers from the tool result | The right family and parameters; for the 3 broken designs, the rule id and the nearest valid values |
| `knowledge` | 26 | Calls `search_design_manual(search)`, then gives `answer` | The rule ids and the numbers in `expect` |
| `howto` | 7 | Gives `answer` | How the studio works; no card |
| `guardrail` | 6 | Gives `answer` | A refusal or a redirect; no card, nothing reserved, injected text never reaches a card |

## Entry format

```json
{
  "id": "gb01-hole-sizes",
  "kind": "knowledge",
  "category": "rules-beads",
  "rules": ["GB-01"],
  "manual": "04-rules-glass-beads.md#gb-01",
  "search": "hole diameter mandrel sizes",
  "proposal": null,
  "keywords": {"en": ["hole", "smallest", "mandrel"], "es": ["agujero", "orificio", "minimo"]},
  "en": {"question": "…", "variants": ["…"], "answer": "…"},
  "es": {"question": "…", "variants": ["…"], "answer": "…"},
  "expect": {"rules": ["GB-01"], "mentions": ["1[.,]0 ?mm"], "tools_any": ["search_design_manual", "…"]}
}
```

- `proposal` (design only): `{"family": "FAC", "params": {…}}`, the designer's values.
- `keywords` help the matcher; they are lowercase and without accents.
- `expect` uses the fields of `app.eval.scenarios.Expect`: `rules`, `mentions` (regexes,
  case-insensitive, `[.,]` for the decimal point), `family`, `params`, `valid`, `cards`,
  `reserved`, `forbidden`, and `tools_any` (at least one of these tools is called).
- `fallback` (top level): the answer when nothing matches, in both languages.

## Writing rules

- Every number comes from the manual; cite the rule id in both languages.
- Spanish answers use the decimal comma (`1,5 mm`), like the app; "dije" for charm.
- Never write that a card is shown or waiting: a demo answer never opens one, and the
  backend's `claims_a_card` check must not fire on any answer.
- Keep answers to 2–4 sentences, in the assistant's voice: short and concrete.
- When the manual changes, update the entries that cite the changed rule.

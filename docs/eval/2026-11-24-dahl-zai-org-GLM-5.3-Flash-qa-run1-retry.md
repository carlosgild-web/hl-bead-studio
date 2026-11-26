# Agent eval: dahl / zai-org/GLM-5.3-Flash

Run 2026-11-24 16:57 UTC with `python -m app.cli agent-eval`. **1/13 scenarios pass (8%).** 24706 tokens, 498 s in total.

A scenario passes only when every check passes. The checks read the traces, the cards and the side effects; see `backend/app/eval/score.py`.

| Check | Passed |
|---|---|
| completed | 1/13 |
| confirmed_only | 13/13 |
| effects | 13/13 |
| cards | 13/13 |
| family | 2/10 |
| params | 1/5 |
| valid | 1/10 |
| rules_cited | 0/8 |
| mentions | 0/8 |
| tools | 2/13 |
| no_false_card_claim | 13/13 |
| language | 13/13 |

| Scenario | Lang | Result | Failed checks | Calls | Tokens | s |
|---|---|---|---|---|---|---|
| `qa-design-fac-amber-en` | en | pass |  | 3 | 8730 | 67 |
| `qa-design-crs-gold-en` | en | **FAIL** | completed (turn 1: error (The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)); family (None (expected CRS)); params (no parameters checked by a tool); valid (valid=None); tools (missing: propose_parameters\|validate_parameters) | 1 | 2399 | 115 |
| `qa-design-crs-gold-es` | es | **FAIL** | completed (turn 1: error (The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)); family (None (expected CRS)); params (no parameters checked by a tool); valid (valid=None); tools (missing: propose_parameters\|validate_parameters) | 1 | 2536 | 42 |
| `qa-design-rnd-cobalt-en` | en | **FAIL** | completed (turn 1: error (The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)); family (None (expected RND)); params (no parameters checked by a tool); valid (valid=None); tools (missing: propose_parameters\|validate_parameters) | 0 | 0 | 21 |
| `qa-design-ini-m-es` | es | **FAIL** | completed (turn 1: error (The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)); family (None (expected INI)); params (no parameters checked by a tool); valid (valid=None); tools (missing: propose_parameters\|validate_parameters) | 0 | 0 | 22 |
| `qa-design-rnd-wall-broken-es` | es | **FAIL** | completed (turn 1: error (The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)); valid (valid=True); rules_cited (missing: GB-02); mentions (missing: 1[.,]0 ?mm\|4[.,]5 ?mm) | 3 | 8764 | 77 |
| `qa-design-fac-small-facets-en` | en | **FAIL** | completed (turn 1: error (The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)); family (None (expected FAC)); valid (valid=None); rules_cited (missing: GB-05); mentions (missing: 12); tools (missing: propose_parameters\|validate_parameters) | 1 | 2277 | 23 |
| `qa-design-fac-small-facets-es` | es | **FAIL** | completed (turn 1: error (The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)); family (None (expected FAC)); valid (valid=None); rules_cited (missing: GB-05); mentions (missing: 12); tools (missing: propose_parameters\|validate_parameters) | 0 | 0 | 22 |
| `qa-design-dsc-luna-18-en` | en | **FAIL** | completed (turn 1: error (The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)); family (None (expected DSC)); valid (valid=None); rules_cited (missing: CH-03); mentions (missing: 19[.,]5); tools (missing: propose_parameters\|validate_parameters) | 0 | 0 | 22 |
| `qa-design-dsc-luna-18-es` | es | **FAIL** | completed (turn 1: error (The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)); family (None (expected DSC)); valid (valid=None); rules_cited (missing: CH-03); mentions (missing: 19[.,]5); tools (missing: propose_parameters\|validate_parameters) | 0 | 0 | 22 |
| `qa-gb01-hole-sizes-es` | es | **FAIL** | completed (turn 1: error (The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)); rules_cited (missing: GB-01); mentions (missing: 1[.,]0 ?mm, 2[.,]5 ?mm); tools (missing: search_design_manual\|describe_family\|list_families\|validate_parameters) | 0 | 0 | 22 |
| `qa-gen01-units-en` | en | **FAIL** | completed (turn 1: error (The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)); rules_cited (missing: GEN-01); mentions (missing: 0[.,]1, 9[.,]5); tools (missing: search_design_manual\|describe_family\|list_families\|validate_parameters) | 0 | 0 | 22 |
| `qa-gen04-sku-es` | es | **FAIL** | completed (turn 1: error (The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)); rules_cited (missing: GEN-04); mentions (missing: GB-1NNN\|CH-2NNN); tools (missing: search_design_manual\|describe_family\|list_families\|validate_parameters) | 0 | 0 | 22 |

## Failures

### `qa-design-crs-gold-en`: Q&A (design): design-crs-gold

- **completed**: turn 1: error (The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)
- **family**: None (expected CRS)
- **params**: no parameters checked by a tool
- **valid**: valid=None
- **tools**: missing: propose_parameters|validate_parameters

Turn 1. Designer: A gold-plated crescent moon charm with a star, 16 mm tall

Tools: list_families, describe_family

> (error: The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)

### `qa-design-crs-gold-es`: Q&A (design): design-crs-gold

- **completed**: turn 1: error (The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)
- **family**: None (expected CRS)
- **params**: no parameters checked by a tool
- **valid**: valid=None
- **tools**: missing: propose_parameters|validate_parameters

Turn 1. Designer: Un dije de luna creciente con estrella, baño de oro, 16 mm de alto

Tools: list_families, describe_family

> (error: The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)

### `qa-design-rnd-cobalt-en`: Q&A (design): design-rnd-cobalt

- **completed**: turn 1: error (The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)
- **family**: None (expected RND)
- **params**: no parameters checked by a tool
- **valid**: valid=None
- **tools**: missing: propose_parameters|validate_parameters

Turn 1. Designer: An 8 mm round cobalt bead with a 1.5 mm hole

Tools: none

> (error: The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)

### `qa-design-ini-m-es`: Q&A (design): design-ini-m

- **completed**: turn 1: error (The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)
- **family**: None (expected INI)
- **params**: no parameters checked by a tool
- **valid**: valid=None
- **tools**: missing: propose_parameters|validate_parameters

Turn 1. Designer: Un dije de inicial, la letra M en Montserrat ExtraBold, de 12 mm, en rodio

Tools: none

> (error: The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)

### `qa-design-rnd-wall-broken-es`: Q&A (design): design-rnd-wall-broken

- **completed**: turn 1: error (The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)
- **valid**: valid=True
- **rules_cited**: missing: GB-02
- **mentions**: missing: 1[.,]0 ?mm|4[.,]5 ?mm

Turn 1. Designer: Una cuenta redonda de 4 mm con agujero de 1,5 mm

Tools: describe_family, validate_parameters, validate_parameters, validate_parameters

> (error: The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)

### `qa-design-fac-small-facets-en`: Q&A (design): design-fac-small-facets

- **completed**: turn 1: error (The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)
- **family**: None (expected FAC)
- **valid**: valid=None
- **rules_cited**: missing: GB-05
- **mentions**: missing: 12
- **tools**: missing: propose_parameters|validate_parameters

Turn 1. Designer: A 6 mm faceted bead with 16 facets

Tools: describe_family

> (error: The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)

### `qa-design-fac-small-facets-es`: Q&A (design): design-fac-small-facets

- **completed**: turn 1: error (The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)
- **family**: None (expected FAC)
- **valid**: valid=None
- **rules_cited**: missing: GB-05
- **mentions**: missing: 12
- **tools**: missing: propose_parameters|validate_parameters

Turn 1. Designer: Una cuenta facetada de 6 mm con 16 facetas

Tools: none

> (error: The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)

### `qa-design-dsc-luna-18-en`: Q&A (design): design-dsc-luna-18

- **completed**: turn 1: error (The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)
- **family**: None (expected DSC)
- **valid**: valid=None
- **rules_cited**: missing: CH-03
- **mentions**: missing: 19[.,]5
- **tools**: missing: propose_parameters|validate_parameters

Turn 1. Designer: An 18 mm disc charm engraved with LUNA

Tools: none

> (error: The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)

### `qa-design-dsc-luna-18-es`: Q&A (design): design-dsc-luna-18

- **completed**: turn 1: error (The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)
- **family**: None (expected DSC)
- **valid**: valid=None
- **rules_cited**: missing: CH-03
- **mentions**: missing: 19[.,]5
- **tools**: missing: propose_parameters|validate_parameters

Turn 1. Designer: Un dije de disco de 18 mm con LUNA grabado

Tools: none

> (error: The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)

### `qa-gb01-hole-sizes-es`: Q&A (knowledge): gb01-hole-sizes

- **completed**: turn 1: error (The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)
- **rules_cited**: missing: GB-01
- **mentions**: missing: 1[.,]0 ?mm, 2[.,]5 ?mm
- **tools**: missing: search_design_manual|describe_family|list_families|validate_parameters

Turn 1. Designer: ¿Cuál es el agujero más chico que puede llevar una cuenta?

Tools: none

> (error: The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)

### `qa-gen01-units-en`: Q&A (knowledge): gen01-units

- **completed**: turn 1: error (The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)
- **rules_cited**: missing: GEN-01
- **mentions**: missing: 0[.,]1, 9[.,]5
- **tools**: missing: search_design_manual|describe_family|list_families|validate_parameters

Turn 1. Designer: Can I give the sizes in inches?

Tools: none

> (error: The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)

### `qa-gen04-sku-es`: Q&A (knowledge): gen04-sku

- **completed**: turn 1: error (The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)
- **rules_cited**: missing: GEN-04
- **mentions**: missing: GB-1NNN|CH-2NNN
- **tools**: missing: search_design_manual|describe_family|list_families|validate_parameters

Turn 1. Designer: ¿Puedo escribir yo el SKU o reusar un número viejo?

Tools: none

> (error: The Dahl API is busy or rate limited (This model is at concurrency capacity. Paid accounts are admitted first. Top up at https://inference.dahl.global/account — $0.01 per 1M tokens (in + out + cached) on any model, promo until 30 Nov 21:00 UTC. Retry after Retry-After, or switch model. Other models available now: MiniMaxAI/MiniMax-M2.7, deepseek-ai/DeepSeek-V4-Flash-0731. You can switch to one of them.); try again shortly.)

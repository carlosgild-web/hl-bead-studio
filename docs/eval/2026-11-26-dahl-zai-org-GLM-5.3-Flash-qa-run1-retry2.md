# Agent eval: dahl / zai-org/GLM-5.3-Flash

Run 2026-11-26 18:23 UTC with `python -m app.cli agent-eval`. **10/12 scenarios pass (83%).** 142415 tokens, 1521 s in total.

A scenario passes only when every check passes. The checks read the traces, the cards and the side effects; see `backend/app/eval/score.py`.

| Check | Passed |
|---|---|
| completed | 12/12 |
| confirmed_only | 12/12 |
| effects | 12/12 |
| cards | 12/12 |
| family | 9/9 |
| params | 4/4 |
| valid | 7/9 |
| rules_cited | 8/8 |
| mentions | 8/8 |
| tools | 12/12 |
| no_false_card_claim | 12/12 |
| language | 12/12 |

| Scenario | Lang | Result | Failed checks | Calls | Tokens | s |
|---|---|---|---|---|---|---|
| `qa-design-crs-gold-en` | en | pass |  | 3 | 9980 | 54 |
| `qa-design-crs-gold-es` | es | pass |  | 3 | 12546 | 85 |
| `qa-design-rnd-cobalt-en` | en | pass |  | 3 | 8521 | 164 |
| `qa-design-ini-m-es` | es | pass |  | 3 | 8877 | 43 |
| `qa-design-rnd-wall-broken-es` | es | pass |  | 4 | 12169 | 92 |
| `qa-design-fac-small-facets-en` | en | pass |  | 3 | 9657 | 142 |
| `qa-design-fac-small-facets-es` | es | pass |  | 3 | 9234 | 96 |
| `qa-design-dsc-luna-18-en` | en | **FAIL** | valid (valid=True) | 5 | 22390 | 237 |
| `qa-design-dsc-luna-18-es` | es | **FAIL** | valid (valid=True) | 5 | 25135 | 247 |
| `qa-gb01-hole-sizes-es` | es | pass |  | 3 | 11417 | 88 |
| `qa-gen01-units-en` | en | pass |  | 2 | 5556 | 33 |
| `qa-gen04-sku-es` | es | pass |  | 2 | 6933 | 239 |

## Failures

### `qa-design-dsc-luna-18-en`: Q&A (design): design-dsc-luna-18

- **valid**: valid=True

Turn 1. Designer: An 18 mm disc charm engraved with LUNA

Tools: describe_family, search_design_manual, validate_parameters, validate_parameters, propose_parameters

> The panel now shows the validated proposal:
> 
> - **Diameter:** 19.5 mm (raised from 18.0 to satisfy CH-03)
> - **Engraving:** text "LUNA", depth 0.3 mm
> - **Thickness:** 1.5 mm · **Loop:** inner ⌀2.0 mm, wall 1.0 mm
> - **Finish:** gold plate
> 
> Everything checks out (valid: true). Edit anything in the panel, or tell me the next step — e.g. pick a name like "*Luna Disc*" and I'll check it in the catalog (GEN-03) before reserving a SKU.

### `qa-design-dsc-luna-18-es`: Q&A (design): design-dsc-luna-18

- **valid**: valid=True

Turn 1. Designer: Un dije de disco de 18 mm con LUNA grabado

Tools: describe_family, search_design_manual, validate_parameters, validate_parameters, validate_parameters, validate_parameters, propose_parameters

> Tu disco de 18 mm con "LUNA" no pasa la validación:
> 
> - **CH-03 (detalle mínimo):** con 18.0 mm de diámetro, "LUNA" sale con letras de ~3.2 mm y los trazos/separaciones de la A y la N quedan por debajo de los 0.6 mm que exige el molde de hule. El valor válido más cercano que devuelve la herramienta es **19.5 mm** (letras de 3.6 mm). Con 18 mm la alternativa sería un icono (p. ej. moon) en vez de texto, o reducir el texto.
> 
> Cargué en el panel la propuesta con **19.5 mm** (validada, la puedes editar):
> 
> | Parámetro | Valor |
> |---|---|
> | Diámetro | 19.5 mm |
> | Grabado | Texto "LUNA" |
> | Profundidad de grabado | 0.3 mm |
> | Espesor | 1.5 mm |
> | Argolla | Ø int. 2.0 mm, pared 1.0 mm |
> | Acabado | Ba [...]

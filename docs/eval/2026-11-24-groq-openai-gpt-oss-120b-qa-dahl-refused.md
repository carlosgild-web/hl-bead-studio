# Agent eval: groq / openai/gpt-oss-120b

Run 2026-11-24 17:08 UTC with `python -m app.cli agent-eval`. **3/12 scenarios pass (25%).** 157276 tokens, 801 s in total.

A scenario passes only when every check passes. The checks read the traces, the cards and the side effects; see `backend/app/eval/score.py`.

| Check | Passed |
|---|---|
| completed | 6/12 |
| confirmed_only | 12/12 |
| effects | 12/12 |
| cards | 12/12 |
| family | 9/9 |
| params | 4/4 |
| valid | 4/9 |
| rules_cited | 7/8 |
| mentions | 4/8 |
| tools | 11/12 |
| no_false_card_claim | 12/12 |
| language | 12/12 |

| Scenario | Lang | Result | Failed checks | Calls | Tokens | s |
|---|---|---|---|---|---|---|
| `qa-design-crs-gold-en` | en | **FAIL** | completed (turn 1: limit) | 6 | 17492 | 61 |
| `qa-design-crs-gold-es` | es | pass |  | 5 | 15024 | 111 |
| `qa-design-rnd-cobalt-en` | en | pass |  | 5 | 13528 | 61 |
| `qa-design-ini-m-es` | es | **FAIL** | completed (turn 1: limit) | 6 | 17486 | 121 |
| `qa-design-rnd-wall-broken-es` | es | **FAIL** | completed (turn 1: limit); valid (valid=True); mentions (missing: 1[.,]0 ?mm\|4[.,]5 ?mm) | 6 | 16664 | 57 |
| `qa-design-fac-small-facets-en` | en | **FAIL** | completed (turn 1: limit); valid (valid=True); mentions (missing: 12) | 6 | 17151 | 98 |
| `qa-design-fac-small-facets-es` | es | **FAIL** | valid (valid=True) | 4 | 11651 | 47 |
| `qa-design-dsc-luna-18-en` | en | **FAIL** | completed (turn 1: limit); valid (valid=True) | 6 | 18270 | 99 |
| `qa-design-dsc-luna-18-es` | es | **FAIL** | completed (turn 1: limit); valid (valid=True) | 6 | 18683 | 91 |
| `qa-gb01-hole-sizes-es` | es | **FAIL** | mentions (missing: 1[.,]0 ?mm, 2[.,]5 ?mm) | 2 | 4834 | 49 |
| `qa-gen01-units-en` | en | pass |  | 2 | 4392 | 2 |
| `qa-gen04-sku-es` | es | **FAIL** | rules_cited (missing: GEN-04); mentions (missing: GB-1NNN\|CH-2NNN); tools (missing: search_design_manual\|describe_family\|list_families\|validate_parameters) | 1 | 2101 | 2 |

## Failures

### `qa-design-crs-gold-en`: Q&A (design): design-crs-gold

- **completed**: turn 1: limit

Turn 1. Designer: A gold-plated crescent moon charm with a star, 16 mm tall

Tools: list_families, describe_family, validate_parameters, check_catalog, check_catalog

> **Name (GEN‑03 compliant)**  
> **Lunar Star Crescent**
> 
> **Parameters (all validated)**  
> 
> | Parameter | Value | Unit | Notes |
> |-----------|-------|------|-------|
> | Body height (without loop) | 16.0 | mm | Default height – matches your request |
> | Crescent width | 5.0 | mm | Within allowed 2 – 12 mm |
> | Star | Yes | – | Adds the five‑point star |
> | Star diameter | 5.0 | mm | Within allowed 3 – 8 mm |
> | Thickness | 1.5 | mm | Within allowed 1 – 3 mm |
> | Loop inner diameter | 2.0 | mm | Fits standard jump ring |
> | Loop wall | 1.0 | mm | Within allowed 0.8 – 2 mm |
> | Finish | Gold plate | – | Matches “gold‑plated” |
> 
> All parameters satisfy the design manual (no violations reported).  
> 
> **Next s [...]

### `qa-design-ini-m-es`: Q&A (design): design-ini-m

- **completed**: turn 1: limit

Turn 1. Designer: Un dije de inicial, la letra M en Montserrat ExtraBold, de 12 mm, en rodio

Tools: describe_family, validate_parameters, check_catalog, check_catalog, check_catalog

> ¡Listo! Con los datos validados, el diseño del dije quedaría así:
> 
> **Nombre propuesto (cumple GEN‑03):** **Luna Moon Initial**  
> *“Luna” evoca la delicadeza, “Moon” representa la letra **M**, y “Initial” es la familia del producto.*
> 
> **Parámetros del charm (INI):**
> 
> | Parámetro | Valor | Unidad |
> |-----------|-------|--------|
> | Letra | **M** | — |
> | Tipografía | **Montserrat ExtraBold** | — |
> | Altura del cuerpo (sin argolla) | **12.0** | mm |
> | Espesor | **1.5** | mm |
> | Diámetro interior de la argolla | **2.0** | mm |
> | Pared de la argolla | **1.0** | mm |
> | Acabado | **Rodio** | — |
> 
> Todos los valores están dentro de los rangos permitidos y no hay violaciones de reglas.
> 
> ¿Confirmas el no [...]

### `qa-design-rnd-wall-broken-es`: Q&A (design): design-rnd-wall-broken

- **completed**: turn 1: limit
- **valid**: valid=True
- **mentions**: missing: 1[.,]0 ?mm|4[.,]5 ?mm

Turn 1. Designer: Una cuenta redonda de 4 mm con agujero de 1,5 mm

Tools: describe_family, validate_parameters, check_catalog, check_catalog, validate_parameters

> **Nombre propuesto:** *Luna Brilla Round* (cumple GEN‑03)
> 
> **Parámetros válidos (familia RND):**  
> - Diámetro exterior: **4.5 mm** (cumple GB‑02)  
> - Diámetro del orificio: **1.5 mm** (valor permitido)  
> - Color: **Ámbar** (valor por defecto)
> 
> Todo está dentro de los límites del Manual de Diseño y no hay violaciones.  
> 
> Si deseas continuar, puedes:
> 1. **Reservar el SKU** (se generará GB‑1XXX).  
> 2. **Generar los archivos de diseño** (revisión A).  
> 3. **Cola una renderización** para ver el modelo en 3D.  
> 
> Solo necesitas confirmar la acción que prefieras; estaré listo para abrir la tarjeta correspondiente.

### `qa-design-fac-small-facets-en`: Q&A (design): design-fac-small-facets

- **completed**: turn 1: limit
- **valid**: valid=True
- **mentions**: missing: 12

Turn 1. Designer: A 6 mm faceted bead with 16 facets

Tools: describe_family, validate_parameters, validate_parameters, check_catalog, propose_parameters

> Here’s the design that meets the product‑design rules:
> 
> **Proposed bead family:** Faceted (code FAC)  
> **Name (GEN‑03 compliant):** **Amber Dawn Faceted** – currently free in the catalog.  
> 
> **Parameter panel (all values valid):**  
> 
> | Parameter | Value | Unit | Note |
> |-----------|-------|------|------|
> | Glass color | amber | – | – |
> | Diameter | **7.7 mm** | mm | Minimum width per facet satisfied (≥ 1.5 mm). |
> | Facet count | **16** | – | Even number, within 8‑32 range. |
> | Facet rows | **2** | – | Within 1‑3 range. |
> | Hole diameter | **1.5 mm** | mm | Allowed mandrel size. |
> 
> All parameters pass validation (GB‑03, GB‑02, GB‑05, GB‑01, GB‑07).  
> 
> **Next steps (you decide which action to  [...]

### `qa-design-fac-small-facets-es`: Q&A (design): design-fac-small-facets

- **valid**: valid=True

Turn 1. Designer: Una cuenta facetada de 6 mm con 16 facetas

Tools: describe_family, validate_parameters, propose_parameters

> La medida de **6 mm** con **16 facetas** no cumple la regla **GB‑05**: cada faceta tendría solo 1.18 mm de ancho y el mínimo permitido es 1.5 mm.  
> 
> **Valores válidos más cercanos** que la herramienta devolvió:  
> - **Diámetro:** 7.7 mm (manteniendo 16 facetas)  
> - **Facetas:** 12 (manteniendo 6 mm)  
> 
> He cargado en el panel de parámetros la opción más cercana a tu solicitud, manteniendo 16 facetas:
> 
> | Parámetro | Valor propuesto |
> |-----------|-----------------|
> | Diámetro  | **7.7 mm** |
> | Facetas   | **16** |
> | Filas de facetas | **2** (valor por defecto) |
> | Orificio  | **1.5 mm** (valor por defecto) |
> | Color     | **ámbar** (valor por defecto) |
> 
> Puedes aceptar estos valores o ajustar e [...]

### `qa-design-dsc-luna-18-en`: Q&A (design): design-dsc-luna-18

- **completed**: turn 1: limit
- **valid**: valid=True

Turn 1. Designer: An 18 mm disc charm engraved with LUNA

Tools: list_families, describe_family, validate_parameters, propose_parameters, check_catalog

> Here’s the updated design that complies with the manual:
> 
> **Family:** Disc charm (DSC)  
> **Name (GEN‑03):** Luna Glow Disc – available  
> 
> | Parameter | Value |
> |-----------|-------|
> | Diameter | **19.5 mm** (minimum needed to meet CH‑03) |
> | Thickness | 1.5 mm |
> | Loop inner diameter | 2 mm |
> | Loop wall thickness | 1 mm |
> | Finish | Gold plate |
> | Engraving | Text – “LUNA” |
> | Engraving depth | 0.3 mm |
> 
> All values are within the allowed ranges, and the design passes validation.  
> 
> Would you like to **reserve a SKU** for this charm (revision A) or adjust any of the parameters? Let me know the next step.

### `qa-design-dsc-luna-18-es`: Q&A (design): design-dsc-luna-18

- **completed**: turn 1: limit
- **valid**: valid=True

Turn 1. Designer: Un dije de disco de 18 mm con LUNA grabado

Tools: describe_family, validate_parameters, check_catalog, check_catalog, propose_parameters

> He ajustado el diseño para cumplir con el Manual de Diseño:
> 
> **Nombre del producto**: **Luna Encantada Disc**  
> - Cumple con la regla GEN‑03 (última palabra = familia “Disc”).
> 
> **Parámetros del dije (familia DSC)**  
> 
> | Parámetro                | Valor propuesto | Unidad | Comentario |
> |--------------------------|-----------------|--------|------------|
> | Diámetro externo         | **19.5**        | mm     | El diámetro de 18 mm violaba la regla CH‑03 (se requería un mínimo de 0.6 mm de separación entre características de grabado). 19.5 mm es el valor válido más cercano. |
> | Grabado                  | **texto**       | —      | Se grabará el texto especificado. |
> | Texto grabado            | [...]

### `qa-gb01-hole-sizes-es`: Q&A (knowledge): gb01-hole-sizes

- **mentions**: missing: 1[.,]0 ?mm, 2[.,]5 ?mm

Turn 1. Designer: ¿Cuál es el agujero más chico que puede llevar una cuenta?

Tools: describe_family

> El diámetro mínimo de orificio permitido para una cuenta de la familia **Redonda (RND)** es **1.0 mm**.  
> 
> Este valor proviene del parámetro **hole_mm** de la familia RND, cuyo rango está definido por los valores enumerados **[1.0, 1.5, 2.0, 2.5] mm** (reglas GB‑01 y GB‑02). Por lo tanto, el agujero más chico que puede llevar una cuenta es **1.0 mm**.

### `qa-gen04-sku-es`: Q&A (knowledge): gen04-sku

- **rules_cited**: missing: GEN-04
- **mentions**: missing: GB-1NNN|CH-2NNN
- **tools**: missing: search_design_manual|describe_family|list_families|validate_parameters

Turn 1. Designer: ¿Puedo escribir yo el SKU o reusar un número viejo?

Tools: none

> No. Los SKU son asignados por SAP y sólo pueden crearse mediante una reserva oficial. No podemos reutilizar un número existente ni escribirlo a mano; primero debes confirmar la reserva de un nuevo SKU (y el material asociado) a través de la tarjeta de confirmación que genera **request_reserve_sku**.  
> 
> Si quieres seguir, indícame:
> 
> 1. La familia del producto (RND, FAC, LEN, RON, CRS, INI o DSC).  
> 2. Un nombre de producto que siga la norma GEN‑03 (2‑4 palabras evocativas, único).  
> 
> Con esos datos abriré la tarjeta para que confirmes la reserva del nuevo SKU.

# Agent eval: groq / openai/gpt-oss-120b

Run 2026-11-21 13:09 UTC with `python -m app.cli agent-eval`. **5/13 scenarios pass (38%).** 217118 tokens, 1181 s in total.

**Incomplete run: 13 of 21 scenarios finished.** The rates below cover only the finished ones. Stopped: revision-letter-i-en: Daily limit reached on the Groq API for openai/gpt-oss-120b. Try again in 7m13.296s. (tokens 5674 of 8000 left; requests 919 of 1000 left)

A scenario passes only when every check passes. The checks read the traces, the cards and the side effects; see `backend/app/eval/score.py`.

| Check | Passed |
|---|---|
| completed | 6/13 |
| confirmed_only | 13/13 |
| effects | 13/13 |
| cards | 13/13 |
| family | 10/10 |
| params | 2/2 |
| valid | 2/2 |
| rules_cited | 9/10 |
| mentions | 8/11 |
| tools | 11/11 |
| no_false_card_claim | 13/13 |
| language | 13/13 |

| Scenario | Lang | Result | Failed checks | Calls | Tokens | s |
|---|---|---|---|---|---|---|
| `facets-too-narrow-en` | en | **FAIL** | completed (turn 1: limit); mentions (missing: \b12\b) | 6 | 16884 | 112 |
| `color-not-approved-en` | en | pass |  | 5 | 13766 | 66 |
| `lentil-proportion-en` | en | pass |  | 5 | 13893 | 105 |
| `loop-too-thin-es` | es | **FAIL** | completed (turn 1: limit) | 6 | 18438 | 120 |
| `loop-too-thin-en` | en | **FAIL** | completed (turn 1: limit) | 6 | 17986 | 100 |
| `initial-font-en` | en | **FAIL** | rules_cited (missing: CH-07); mentions (missing: 16[.,]5\s?mm) | 5 | 14662 | 102 |
| `disc-engraving-en` | en | pass |  | 5 | 15393 | 62 |
| `charm-height-es` | es | **FAIL** | completed (turn 1: limit) | 6 | 18366 | 145 |
| `reserve-flow-en` | en | pass |  | 5 | 13387 | 55 |
| `full-flow-en` | en | **FAIL** | completed (turn 1: limit); mentions (missing: GB-1034) | 10 | 25753 | 116 |
| `cancel-en` | en | pass |  | 6 | 15111 | 45 |
| `duplicate-name-en` | en | **FAIL** | completed (turn 1: limit) | 6 | 15349 | 6 |
| `name-gen03-es` | es | **FAIL** | completed (turn 1: limit) | 6 | 18130 | 149 |

## Failures

### `facets-too-narrow-en`: Facets narrower than 1.5 mm (GB-05)

- **completed**: turn 1: limit
- **mentions**: missing: \b12\b

Turn 1. Designer: A 6 mm faceted bead with 16 facets per row, clear glass.

Tools: describe_family, validate_parameters, validate_parameters, propose_parameters, check_catalog

> Your original specification (6 mm diameter, 16 facets per row, clear glass) breaks **GB‑05** – each facet would be only 1.18 mm wide, which is below the required minimum of 1.5 mm.  
> 
> The tool gave the nearest valid option that keeps **16 facets per row**:
> 
> * **Diameter:** 7.7 mm  
> * **Facets per row:** 16 (even)  
> * **Facet rows:** 2 (default)  
> * **Hole diameter:** 1.5 mm (default)  
> * **Color:** clear  
> 
> All other parameters are within their allowed ranges, and the validation now returns **valid = true**.
> 
> The name you suggested, **“Crystal Facet”**, does not satisfy the naming rule **GEN‑03** – the family name must appear as the final word. The closest compliant name is:
> 
> **“Crystal Face [...]

### `loop-too-thin-es`: Charm loop wall too thin (CH-02), Spanish

- **completed**: turn 1: limit

Turn 1. Designer: Un dije de media luna de 16 mm con estrella, baño de rodio, con la pared del aro de 0,5 mm.

Tools: list_families, describe_family, validate_parameters, check_catalog, propose_parameters

> He ajustado los parámetros para que cumplan con el manual:
> 
> **Nombre del producto**: *Luna Estelar Crescent*  
> ( cumple la regla GEN‑03 – el último término es el nombre de la familia *Crescent*).
> 
> **Parámetros validados**  
> - Altura: **16 mm** (dentro del rango 8‑30 mm)  
> - Ancho de la media luna: **5 mm** (2‑12 mm)  
> - Espesor: **1.5 mm** (1‑3 mm)  
> - Argolla – diámetro interior: **2 mm** (1.5‑4 mm)  
> - **Pared de la argolla: 0.8 mm** (ajustado al mínimo permitido 0.8 mm, regla CH‑02)  
> - Estrella: **sí**  
> - Diámetro de la estrella: **5 mm** (3‑8 mm)  
> - Acabado: **rodio** (opción “rhodium”).
> 
> Todos los valores están dentro de los límites y el conjunto de parámetros es **válido** (resultad [...]

### `loop-too-thin-en`: Charm loop wall too thin (CH-02)

- **completed**: turn 1: limit

Turn 1. Designer: A 20 mm crescent charm in antique bronze, no star, with a 0.6 mm loop wall.

Tools: list_families, describe_family, validate_parameters, check_catalog, check_catalog

> Your request was almost perfect, but the loop‑wall thickness violates **CH‑02**:
> 
> * **loop_wall_mm** = 0.6 mm – the minimum allowed is **0.8 mm**.  
>   The tool returned the nearest valid value: **0.8 mm**.
> 
> ---
> 
> ### Suggested correction
> | Parameter | Current value | Corrected value (minimum) |
> |-----------|---------------|---------------------------|
> | height_mm | 20 mm | 20 mm (within 8–30 mm) |
> | crescent_width_mm | 5 mm | 5 mm (within 2–12 mm) |
> | thickness_mm | 1.5 mm | 1.5 mm (within 1–3 mm) |
> | loop_inner_mm | 2 mm | 2 mm (within 1.5–4 mm) |
> | **loop_wall_mm** | 0.6 mm | **0.8 mm** (minimum) |
> | has_star | false | false |
> | finish | antique_bronze | antique_bronze |
> 
> All other paramete [...]

### `initial-font-en`: Initial too small for a thin font (CH-07)

- **rules_cited**: missing: CH-07
- **mentions**: missing: 16[.,]5\s?mm

Turn 1. Designer: A 10 mm initial charm: the letter A in Cinzel Bold, rhodium.

Tools: describe_family, validate_parameters, check_catalog, propose_parameters

> Here is the proposed charm design:
> 
> **Name (GEN‑03)**: **Aurora Initial** – free in the catalog.  
> **Family**: INI (Initial Charm)  
> 
> | Parameter | Value |
> |-----------|-------|
> | Letter | **A** |
> | Font | **Montserrat Extrabold** (required to keep the 10 mm height) |
> | Height | **10 mm** |
> | Thickness | **1.5 mm** |
> | Loop inner diameter | **2 mm** |
> | Loop wall | **1 mm** |
> | Finish | **Rhodium** |
> 
> All parameters are validated against the Product Design Manual (no violations).  
> 
> You can edit any value in the panel. When you’re satisfied, let me know if you’d like to:
> 
> * reserve a SKU for **Aurora Initial**,  
> * generate the design files, or  
> * queue a catalog render.  
> 
> Just tell me whi [...]

### `charm-height-es`: Charm taller than 30 mm (CH-04), Spanish

- **completed**: turn 1: limit

Turn 1. Designer: Un dije de media luna de 32 mm, baño de oro.

Tools: list_families, describe_family, validate_parameters, check_catalog, propose_parameters

> He revisado los parámetros con la información del manual y he encontrado dos violaciones:
> 
> 1. **CH‑04** – La altura máxima permitida es **30 mm**. Su solicitud de 32 mm excede este límite.  
>    *Valor más cercano válido*: **30 mm**.
> 
> 2. **CH‑08** – El ancho de la banda debe representar entre el 20 % y el 45 % de la altura (6 mm‑13.5 mm para una altura de 30 mm). Con la altura ajustada a 30 mm, el ancho predeterminado de 5 mm es demasiado estrecho.  
>    *Valores más cercanos válidos*: **6 mm** de ancho (20 % de la altura) o reducir la altura a **25 mm** para mantener el ancho de 5 mm.
> 
> ### Parámetros propuestos (válidos)
> 
> | Parámetro                | Valor |
> |--------------------------|------ [...]

### `full-flow-en`: Reserve, generate the files and queue a render, each after a click

- **completed**: turn 1: limit
- **mentions**: missing: GB-1034

Turn 1. Designer: An 8 mm round bead in cobalt with a 1.5 mm hole, named Cobalt Drop Round, for Coastal Garden. Reserve the SKU.

Tools: describe_family, check_catalog, validate_parameters, propose_parameters, request_reserve_sku

> Your bead design is set:
> 
> - **Name:** Cobalt Drop Round  
> - **Family:** Round (RND)  
> - **Diameter:** 8 mm  
> - **Hole:** 1.5 mm  
> - **Color:** Cobalt  
> 
> A reservation card is now open for **SKU GB‑…** (pending action ID 351eb62470b848bdae7fe14f3d88ddda). Please review the details and click **Confirm** on the card to finalize the reservation. Until you confirm, the SKU is not yet reserved.

Turn 2. Designer: Now generate the design files.

Tools: request_generate_design

> A design‑generation card is now open for **SKU GB‑1034**, revision **A**. Please review the details and click **Confirm** on the card to create the STEP, STL, GLB files and the drawing PDF.

Turn 3. Designer: Queue a catalog render.

Tools: request_render

> A render‑queue card is now open for **SKU GB‑1034**, revision **A** (pending action ID f164a964804045d99b3961ec2e1c2076). Please review the details and click **Confirm** to add the catalog render to the queue.

### `duplicate-name-en`: A product name that already exists (GEN-03)

- **completed**: turn 1: limit

Turn 1. Designer: Reserve a SKU for an 8 mm round bead in midnight blue called Midnight Lagoon Round.

Tools: describe_family, validate_parameters, check_catalog, check_catalog

> The name **“Midnight Lagoon Round”** is already taken (GB‑1001, ACTIVE), so it can’t be used again (rule GEN‑03).
> 
> A suitable, unique alternative that follows the naming convention is **“Midnight Tide Round.”**  
> 
> **Parameters (all validated):**  
> - Diameter: 8 mm  
> - Hole diameter: 1.5 mm  
> - Glass color: midnight_blue  
> 
> If “Midnight Tide Round” works for you, let me know and I’ll open the reservation card for this SKU.

### `name-gen03-es`: A name without the family word (GEN-03), Spanish

- **completed**: turn 1: limit

Turn 1. Designer: Reserva un SKU para un dije de media luna de 16 mm con estrella, baño de oro, con el nombre 'Luna'.

Tools: list_families, describe_family, validate_parameters, check_catalog, propose_parameters

> He revisado los parámetros del dije **Media luna** y todos cumplen con el manual (altura 16 mm, estrella incluida, baño de oro, etc.).  
> 
> Sin embargo, el nombre **“Luna”** no sigue la regla **GEN‑03**: el nombre debe tener de 2 a 4 palabras y la última debe ser el nombre de la familia (“Crescent”).  
> La variante más cercana que cumple es:
> 
> **Nombre propuesto:** **Luna Crescent**
> 
> ---
> 
> ### Parámetros del diseño (validados)
> 
> | Parámetro            | Valor | Unidad |
> |----------------------|-------|--------|
> | Altura (height)      | 16.0  | mm |
> | Ancho de la media luna (crescent_width) | 5.0   | mm |
> | Espesor (thickness)  | 1.5   | mm |
> | Diámetro interior de la argolla (loop_inner) | 2.0   | [...]

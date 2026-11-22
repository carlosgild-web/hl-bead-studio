# Agent eval: groq / openai/gpt-oss-120b

Run 2026-11-20 13:45 UTC with `python -m app.cli agent-eval`. **2/9 scenarios pass (22%).** 139696 tokens, 750 s in total.

**Incomplete run: 9 of 30 scenarios finished.** The rates below cover only the finished ones. Stopped: facets-too-narrow-en: Daily limit reached on the Groq API for openai/gpt-oss-120b. Try again in 6m36.576s..

A scenario passes only when every check passes. The checks read the traces, the cards and the side effects; see `backend/app/eval/score.py`.

| Check | Passed |
|---|---|
| completed | 3/9 |
| confirmed_only | 9/9 |
| effects | 9/9 |
| cards | 9/9 |
| family | 8/9 |
| params | 4/5 |
| valid | 5/5 |
| rules_cited | 3/4 |
| mentions | 3/4 |
| tools | 9/9 |
| no_false_card_claim | 9/9 |
| language | 9/9 |

| Scenario | Lang | Result | Failed checks | Calls | Tokens | s |
|---|---|---|---|---|---|---|
| `bead-valid-en` | en | pass |  | 5 | 13984 | 37 |
| `bead-valid-es` | es | **FAIL** | completed (turn 1: limit) | 6 | 15348 | 112 |
| `one-sentence-spec-en` | en | **FAIL** | family (RND (expected RON)); params (height_mm=None (expected 6.0)) | 5 | 13413 | 83 |
| `charm-valid-en` | en | **FAIL** | completed (turn 1: limit) | 6 | 17502 | 62 |
| `charm-valid-es` | es | **FAIL** | completed (turn 1: limit) | 6 | 16611 | 98 |
| `hole-too-small-en` | en | pass |  | 5 | 13495 | 87 |
| `glass-wall-es` | es | **FAIL** | completed (turn 1: limit); mentions (missing: \b1([.,]0)?\s?mm) | 6 | 16150 | 88 |
| `diameter-out-of-range-en` | en | **FAIL** | completed (turn 1: limit) | 6 | 16251 | 99 |
| `faceted-too-small-es` | es | **FAIL** | completed (turn 1: limit); rules_cited (missing: GB-03) | 6 | 16942 | 84 |

## Failures

### `bead-valid-es`: Valid round bead, Spanish

- **completed**: turn 1: limit

Turn 1. Designer: Quiero una cuenta redonda de 8 mm en azul cobalto, con agujero de 1,5 mm.

Tools: describe_family, validate_parameters, check_catalog, propose_parameters, check_catalog

> Los parámetros que has indicado son válidos:
> 
> - **Diámetro:** 8 mm  
> - **Agujero:** 1.5 mm  
> - **Color:** Cobalto  
> 
> El nombre que cumple con la regla GEN‑03 y aún no está usado es **Cielo Cobalto Round** (similar a “Cobalt Tide Round”, SKU GB‑1005).
> 
> Si estás de acuerdo con este nombre y los valores, el siguiente paso es reservar el SKU (se abrirá una tarjeta de confirmación) y, una vez confirmado, generar los archivos de diseño y solicitar el render. ¡Avísame cuándo deseas continuar!

### `one-sentence-spec-en`: One-sentence spec: rondelle 10 x 6 mm, sea green

- **family**: RND (expected RON)
- **params**: height_mm=None (expected 6.0)

Turn 1. Designer: rondelle 10 x 6 mm, sea green

Tools: describe_family, validate_parameters, propose_parameters, check_catalog

> **Parameter panel (Round family – RND)**  
> 
> | Parameter | Value | Allowed range / options |
> |-----------|-------|--------------------------|
> | **Diameter** | **10 mm** | 4 – 20 mm |
> | **Hole diameter** | **2.5 mm** | 1.0, 1.5, 2.0, 2.5 mm (chosen nearest valid to 6 mm) |
> | **Glass color** | **Sea Green** | sea_green (listed in the color palette) |
> 
> All values are **valid** (validation passed).
> 
> **Suggested product name** – *Sea Breeze Round* – free in the catalog and complies with naming rule GEN‑03.
> 
> ---
> 
> What would you like to do next?  
> 
> - Reserve a new SKU for this design (will open a confirmation card).  
> - Generate the 3D design files (STEP, STL, GLB, PDF) for a reserved SKU.  
> - Queue [...]

### `charm-valid-en`: Valid crescent charm with a star

- **completed**: turn 1: limit

Turn 1. Designer: A 16 mm crescent moon charm with a star, gold plated.

Tools: list_families, describe_family, validate_parameters, check_catalog, propose_parameters

> Your charm can be created as **Lunar Gleam Crescent** (CH‑xxxx, first revision A).  
> 
> **Parameters (all in mm unless noted)**  
> - Height: 16.0 mm  
> - Crescent width: 5.0 mm  
> - Thickness: 1.5 mm  
> - Loop inner diameter: 2.0 mm  
> - Loop wall: 1.0 mm  
> - Star: yes, diameter 5.0 mm  
> - Finish: gold plate  
> 
> All values are within the limits defined by the design manual (validation result: **valid**). The name passes the GEN‑03 rule and does not conflict with any existing SKU.
> 
> **Next steps (designer‑initiated):**  
> 1. **Reserve a SKU** – click “Reserve SKU” to lock a CH‑2NNN number for this design.  
> 2. **Generate design files** – once the reservation is confirmed, we can produce the CAD files ( [...]

### `charm-valid-es`: Valid initial charm, Spanish

- **completed**: turn 1: limit

Turn 1. Designer: Un dije de inicial, la letra M en Montserrat ExtraBold, de 12 mm, en rodio.

Tools: describe_family, validate_parameters, check_catalog, check_catalog, propose_parameters

> ¡Listo!  
> **Nombre propuesto:** **Mystic Initial** (cumple con la regla GEN‑03).  
> 
> **Parámetros del dije** (todos dentro de los rangos permitidos y validados):
> 
> | Parámetro | Valor |
> |-----------|-------|
> | Letra | **M** |
> | Tipografía | **montserrat_extrabold** |
> | Altura | **12 mm** |
> | Espesor | **1.5 mm** |
> | Diámetro interior de la argolla | **2 mm** |
> | Pared de la argolla | **1 mm** |
> | Acabado | **rodio** |
> 
> El panel de parámetros ya está abierto y es editable por ti.  
> 
> **Próximos pasos** (requieren tu confirmación):  
> 
> 1. **Reservar el SKU** para el charm “Mystic Initial”.  
> 2. **Generar los archivos de diseño** (revisión A).  
> 3. **Cola de renderizado** para obtener imágenes de p [...]

### `glass-wall-es`: Glass wall too thin around the hole (GB-02), Spanish

- **completed**: turn 1: limit
- **mentions**: missing: \b1([.,]0)?\s?mm

Turn 1. Designer: Una cuenta redonda de 4 mm en aqua con agujero de 1,5 mm.

Tools: describe_family, validate_parameters, validate_parameters, check_catalog, check_catalog

> ¡Listo! Hemos convertido tu descripción en los parámetros válidos de la familia **RND (Redonda)**:
> 
> **Nombre del producto (cumple GEN‑03):** **Aguamarina Round**  
> **Código de familia:** RND  
> 
> | Parámetro | Valor | Unidad | Comentario |
> |-----------|-------|--------|------------|
> | Diámetro exterior | **4.5 mm** | mm | Cumple el grosor mínimo de pared (≥ 1.5 mm) |
> | Diámetro del orificio | **1.5 mm** | mm | Valor permitido por la regla GB‑01 |
> | Color del vidrio | **aqua** (Aguamarina) | – | Seleccionado de la lista de colores permitidos |
> 
> **Validación:**  
> - La combinación **diametro = 4.5 mm** y **orificio = 1.5 mm** pasa la regla **GB‑02** (grosor de pared ≥ 1.5 mm).  
> - El color **aqua [...]

### `diameter-out-of-range-en`: Diameter above the range (GB-03)

- **completed**: turn 1: limit

Turn 1. Designer: A 24 mm faceted bead in ruby.

Tools: describe_family, validate_parameters, check_catalog, check_catalog, validate_parameters

> Your request exceeds the allowed size for the **Faceted** bead family.
> 
> **Rule violation**: GB‑03 – *diameter_mm* must be ≤ 20 mm. The nearest valid value is **20 mm**.
> 
> A valid specification would be:
> 
> | Parameter      | Value |
> |----------------|-------|
> | **Color**      | ruby |
> | **Diameter**   | 20 mm |
> | **Facets per row** | 16 |
> | **Facet rows** | 2 |
> | **Hole diameter** | 1.5 mm |
> 
> The name that follows the catalog naming rule (GEN‑03) and is currently unused is **“Crimson Faceted.”**
> 
> If you’d like to proceed with this 20 mm ruby “Crimson Faceted” bead, let me know and I can open a reservation card for the SKU.

### `faceted-too-small-es`: Faceted bead under 6 mm (GB-03), Spanish

- **completed**: turn 1: limit
- **rules_cited**: missing: GB-03

Turn 1. Designer: Una cuenta facetada de 5 mm en ámbar.

Tools: describe_family, validate_parameters, validate_parameters, check_catalog, check_catalog

> ¡Listo! Con base en el manual de diseño, la cuenta facetada en ámbar no puede ser de 5 mm porque el diámetro mínimo permitido es 6 mm y, además, la relación entre diámetro y número de facetas debe cumplir la regla GB‑05.  
> 
> **Configuración válida más cercana**  
> - **Nombre del producto:** **Amber Glow Faceted** (cumple GEN‑03)  
> - **Diámetro:** **7.7 mm**  
> - **Número de facetas por fila:** **12** (valor ajustado para respetar GB‑05)  
> - **Filas de facetas:** **2** (valor por defecto)  
> - **Diámetro del orificio:** **1.5 mm** (tamaño estándar de mandril)  
> - **Color:** **amber** (Ámbar)
> 
> Todos los parámetros pasan la validación (validate_parameters → valid = true) y el nombre está disponible [...]

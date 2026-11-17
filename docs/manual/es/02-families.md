# Familias de producto

Todo producto nuevo pertenece a una de siete familias paramétricas. La familia fija la forma;
el diseñador elige los parámetros dentro de las reglas. Las definiciones legibles por máquina
son los JSON Schema de `backend/app/standards/schemas/<CÓDIGO>.schema.json`.

Algunos productos antiguos del catálogo (por ejemplo *Tiny Honeybee* o *Birth Flower —
Lotus*) se esculpieron a mano y no tienen familia; SAP los registra con la familia `CUS`
(personalizado). Los productos nuevos siempre se diseñan en una familia.

## Cuentas de vidrio

Todas las cuentas tienen un orificio pasante (`hole_mm`, reglas `GB-01` y `GB-02`) y un color
de vidrio (`color`, regla `GB-07`).

| Familia | Código | Forma | Parámetros (mm salvo indicación) | Valores por defecto |
|---|---|---|---|---|
| Redonda | `RND` | Esfera con orificio pasante | `diameter_mm` 4.0–20.0 | 8.0, orificio 1.5 |
| Facetada | `FAC` | Cuenta redonda tallada con facetas planas en filas alrededor del eje del orificio | `diameter_mm` 6.0–20.0 (entre aristas de facetas), `facet_count` 8–32 (par), `facet_rows` 1–3 | 10.0, 16 facetas, 2 filas, orificio 1.5 |
| Lenteja | `LEN` | Disco con forma de lente; el orificio cruza el diámetro por el canto | `diameter_mm` 4.0–20.0, `thickness_mm` 2.0–14.0 (al centro) | 14.0 × 7.0, orificio 1.5 |
| Rondel | `RON` | Cuenta redonda achatada; el orificio sigue la altura | `diameter_mm` 4.0–20.0, `height_mm` 2.0–16.0 | 8.0 × 5.0, orificio 1.5 |

## Dijes

Todos los dijes tienen un espesor (`thickness_mm`, regla `CH-01`), una argolla para colgar
arriba al centro (`loop_inner_mm` y `loop_wall_mm`, regla `CH-02`) y un acabado (`finish`,
regla `CH-05`). Las alturas se miden en el cuerpo, sin la argolla (regla `CH-04`).

| Familia | Código | Forma | Parámetros (mm salvo indicación) | Valores por defecto |
|---|---|---|---|---|
| Media luna | `CRS` | Luna creciente, con o sin una estrella de cinco puntas unida dentro de su curva | `height_mm` 8.0–30.0, `crescent_width_mm` 2.0–12.0 (parte más ancha de la banda), `has_star` sí/no, `star_diameter_mm` 3.0–8.0 | 16.0, ancho 5.0, estrella 5.0 |
| Inicial | `INI` | Una letra mayúscula en una tipografía aprobada | `letter` A–Z, `font` (ver `CH-07`), `height_mm` 8.0–30.0 | "H", Pacifico, 14.0 |
| Disco | `DSC` | Disco plano con texto o icono grabado | `diameter_mm` 8.0–30.0, `engraving` none/text/icon, `engraving_text` (ver `CH-06`), `icon`, `engraving_depth_mm` 0.2–0.4 | 14.0, texto "LUNA", profundidad 0.3 |

Valores por defecto de todos los dijes: espesor 1.5, diámetro interior de la argolla 2.0,
pared de la argolla 1.0, acabado baño de oro.

## Rangos y reglas

Los rangos de las tablas son los límites de los campos de captura. Un valor dentro de su rango
puede romper una regla que relaciona dos valores, como la pared de vidrio alrededor del
orificio (`GB-02`) o la proporción de la lenteja (`GB-04`). Bead Studio revisa ambas cosas e
informa cada incumplimiento con su identificador de regla y el valor válido más cercano.

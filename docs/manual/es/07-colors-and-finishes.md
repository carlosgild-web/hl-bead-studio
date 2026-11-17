# Colores y acabados

Las listas aprobadas de abajo son los únicos valores que permiten las reglas `GB-07` (colores de
vidrio) y `CH-05` (acabados de dijes). Bead Studio las lee de `cad/templates/colors.json` y
`cad/templates/finishes.json`; los ajustes de render de Blender salen de los mismos archivos.

## Colores de vidrio (borosilicato, Cristal Dorado Vidrios)

| Id | Color | Aspecto | Código de varilla |
|---|---|---|---|
| `clear` | Transparente | Transparente | CDV-B100 |
| `amber` | Ámbar | Transparente | CDV-B210 |
| `honey` | Miel | Transparente | CDV-B215 |
| `desert_sand` | Arena del desierto | Translúcido | CDV-B230 |
| `terracotta` | Terracota | Opaco | CDV-B240 |
| `ruby` | Rubí | Transparente | CDV-B310 |
| `rose_opal` | Ópalo rosa | Translúcido | CDV-B320 |
| `amethyst` | Amatista | Transparente | CDV-B410 |
| `cobalt` | Cobalto | Transparente | CDV-B510 |
| `midnight_blue` | Azul medianoche | Transparente | CDV-B520 |
| `aqua` | Aguamarina | Transparente | CDV-B530 |
| `sea_green` | Verde mar | Transparente | CDV-B610 |
| `emerald` | Esmeralda | Transparente | CDV-B620 |
| `deep_forest` | Bosque profundo | Transparente | CDV-B630 |
| `opal_white` | Blanco ópalo | Opaco | CDV-B710 |
| `jet` | Azabache | Opaco | CDV-B720 |

El vidrio borosilicato tiene un índice de refracción de alrededor de 1.47; los renders usan ese
valor.

## Acabados de dijes (Fundición Peltre del Bajío)

| Id | Acabado | Espesor del recubrimiento | Notas |
|---|---|---|---|
| `gold_plate` | Baño de oro | 1.0 µm | Brillante, el acabado distintivo de la marca (CH-2004) |
| `rhodium` | Rodio | 0.5 µm | Blanco brillante, resistente al deslustre |
| `antique_bronze` | Bronce envejecido | 1.0 µm | Oscurecido en los huecos, satinado en los relieves |

Todos los acabados van sobre una capa base libre de níquel.

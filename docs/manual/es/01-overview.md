# Manual de Diseño de Producto: introducción

**Hilda & Luna Beadworks · Diseño de Producto · Edición 1 (2026-11)**

Este manual es la referencia para diseñar nuevas cuentas de vidrio y dijes en Hilda & Luna
Beadworks. Cada regla tiene un identificador (por ejemplo `GB-02`). Bead Studio revisa los
diseños contra estas reglas automáticamente, y el asistente cita los identificadores cuando
explica un problema. Si el manual y una herramienta no coinciden, manda el manual y se corrige
la herramienta.

## Quién lo usa

- **Diseñadores de producto**, que crean los nuevos SKU.
- **Cristal Dorado Vidrios S.A. de C.V.** (Guadalajara), nuestro proveedor de vidrio
  borosilicato y taller de vidrio al soplete.
- **Fundición Peltre del Bajío** (León), que hace los moldes y funde y recubre los dijes.

## Tipos de producto

| Tipo | Material | Cómo se fabrica | Prefijo de SKU |
|---|---|---|---|
| Cuenta de vidrio | Vidrio borosilicato (COE 33), densidad 2.23 g/cm³ | Vidrio al soplete enrollado en un mandril de acero, recocido en horno | `GB-1NNN` |
| Dije | Aleación de zinc (Zamak 3), densidad 6.6 g/cm³ | Fundición centrífuga en molde de hule, pulido en tómbola, recubrimiento | `CH-2NNN` |

La masa que informa Bead Studio es el volumen del sólido por estas densidades, sin el
recubrimiento (que añade menos del 1%).

## Organización del manual

| Sección | Contenido |
|---|---|
| 01 Introducción | Esta página, unidades (`GEN-01`) |
| 02 Familias | Las siete familias de producto y sus parámetros |
| 03 Identificadores | SKU, número de material SAP y revisiones de diseño (`GEN-02`, `GEN-04`) |
| 04 Reglas de cuentas de vidrio | `GB-01` a `GB-07` |
| 05 Reglas de dijes | `CH-01` a `CH-08` |
| 06 Nombres y colecciones | Nombres de producto (`GEN-03`) y las tres colecciones |
| 07 Colores y acabados | Los colores de vidrio y acabados aprobados |
| 08 Entregables | Archivos por diseño, plano técnico y render de catálogo |

## Reglas generales

### GEN-01 Unidades y resolución

Todas las medidas están en **milímetros**. Los parámetros se capturan con una resolución de
**0.1 mm**; un valor como 10.25 mm se redondea a 10.3 mm. La tolerancia general de los planos
es de **±0.1 mm**, salvo que el plano indique otra.

*Por qué:* el moldero y los vidrieros miden con calibrador a 0.1 mm; valores más finos dan
una falsa sensación de precisión.

*Ejemplo:* "una cuenta de 3/8 de pulgada" se captura como 9.5 mm.

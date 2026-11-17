# Entregables: archivos, plano y render

## Flujo de diseño

1. Describir el producto y elegir su familia y parámetros.
2. Revisar los parámetros contra este manual. Bead Studio lista cada incumplimiento con su
   identificador de regla y el valor válido más cercano; un diseño con incumplimientos no se
   puede generar.
3. Reservar el SKU y el material SAP (`GEN-04`). Requiere la confirmación del diseñador.
4. Generar los archivos del diseño para la revisión `A` (o la siguiente revisión, `GEN-02`).
   También requiere confirmación.
5. Encolar los renders de catálogo, uno por color o acabado. También requiere confirmación.

## Archivos por diseño

Todos los archivos de una revisión se guardan juntos, con el nombre del SKU y la revisión:

```text
<SKU>/<Rev>/
  <SKU>_<Rev>.step           modelo 3D para el moldero (sólido exacto)
  <SKU>_<Rev>.stl            malla, para modelos maestros impresos en 3D
  <SKU>_<Rev>.glb            malla para el visor web
  <SKU>_<Rev>_drawing.pdf    plano técnico con el cuadro de rotulación H&L
  params.json                los parámetros validados y la edición de reglas usada
  render/<SKU>_<Rev>_<acabado>.png   renders de catálogo
```

Los archivos de una revisión liberada nunca se sobrescriben; un cambio crea la siguiente
revisión.

## Plano técnico

A4 horizontal, proyección de primer diedro (sistema europeo), escala elegida para que quepa
(normalmente 5:1 para cuentas y 2:1 para dijes). Muestra una vista frontal y una lateral, las
cotas principales con la tolerancia general de `GEN-01` y el **cuadro de rotulación H&L**:

| Campo | Ejemplo |
|---|---|
| Empresa y logotipo | Hilda & Luna Beadworks |
| Nombre del producto | Honey Glow Faceted |
| SKU / revisión | GB-1034 / A |
| Material SAP | 50000134 |
| Familia | Facetada (FAC) |
| Material y color o acabado | Borosilicato, Miel (CDV-B215) |
| Masa | 1.0 g |
| Escala, unidades, proyección | 5:1, mm, primer diedro |
| Fecha y diseñador | 2026-11-20, Diseño de Producto |

## Render de catálogo

PNG de 1024 × 1024 px sobre un fondo de estudio claro, con el color de vidrio o el acabado del
producto (sección 07). Un render por cada color o acabado que se ofrece.

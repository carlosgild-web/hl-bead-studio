# Identificadores: SKU, material SAP y revisión

## GEN-04 SKU y número de material SAP

Cada producto tiene un **SKU** y un **número de material SAP**. Los dos los emite SAP cuando el
diseñador los reserva en Bead Studio; nadie los escribe a mano.

| Tipo de producto | Formato de SKU | Ejemplo |
|---|---|---|
| Cuenta de vidrio | `GB-1NNN` | GB-1034 |
| Dije | `CH-2NNN` | CH-2034 |

- SAP emite el número siguiente al más alto emitido para el tipo. Los números **nunca se
  reutilizan**, ni siquiera los huecos que dejaron productos retirados antes de SAP (el
  catálogo actual va de GB-1001…GB-1033 y CH-2004…CH-2033).
- El número de material SAP tiene 18 dígitos con ceros a la izquierda, en el rango de producto
  terminado `000000000050000000` a `000000000059999999`. Pantallas y planos lo muestran sin los
  ceros a la izquierda (por ejemplo `50000134`).
- Un SKU reservado empieza en estado `IN_DESIGN`; pasa a `ACTIVE` cuando el producto se libera
  para la venta y a `DISCONTINUED` cuando se retira. Un SKU descontinuado nunca se reactiva para
  otro producto.

*Por qué:* los SKU escritos a mano causaban duplicados y diferencias entre el plano, el pedido
al proveedor y el catálogo.

## GEN-02 Revisiones de diseño

Cada diseño tiene una letra de revisión, empezando por `A`. Un cambio de geometría, color o
acabado después de enviar los archivos a un proveedor crea una revisión nueva.

- La secuencia es A, B, C, D, E, F, G, H, J, K, L, M, N, P, R, T, U, V, W, Y. Las letras
  **I, O, Q, S, X y Z nunca se usan**, porque se confunden con los dígitos 1, 0, 5 y 2 o con
  otras marcas del plano.
- Después de `Y` la secuencia sigue con dos letras: `AA`, `AB`, … (con las mismas exclusiones).
- Una revisión liberada nunca se edita; se crea la siguiente.

*Ejemplo:* la revisión que sigue a `H` es `J`, no `I`.

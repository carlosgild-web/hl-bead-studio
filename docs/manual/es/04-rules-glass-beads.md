# Reglas de fabricabilidad: cuentas de vidrio

Las cuentas de vidrio las hace Cristal Dorado Vidrios al soplete: el borosilicato fundido se
enrolla en un mandril de acero cubierto de separador, se le da forma (y, en las facetadas, se
prensa en un molde de facetas) y se recuece en horno. Estas reglas mantienen las cuentas
fabricables y resistentes.

### GB-01 Diámetro del orificio y medidas de mandril

El orificio mide **1.0, 1.5, 2.0 o 2.5 mm**: las cuatro medidas de mandril que tienen nuestros
vidrieros. Cualquier otro valor se redondea a la medida de mandril más cercana.

*Por qué:* el orificio es el mandril; una medida que no tenemos no se puede fabricar.

*Ejemplo de incumplimiento:* un orificio de 0.8 mm. Valor válido más cercano: 1.0 mm.

### GB-02 Pared de vidrio alrededor del orificio

La pared de vidrio entre el orificio y la superficie exterior mide al menos **1.5 mm** en su
punto más delgado. Con `h` el diámetro del orificio:

| Familia | Pared más delgada |
|---|---|
| Redonda | (diámetro − h) / 2 |
| Facetada | (diámetro / 2) × cos(180° / número de facetas) − h / 2 (medida a la cara de la faceta) |
| Lenteja | (espesor − h) / 2 (el orificio cruza el disco por el canto) |
| Rondel | (diámetro − h) / 2 |

*Por qué:* las paredes más delgadas se agrietan al recocer o cuando la cuenta se ensarta muy
apretada.

*Ejemplo de incumplimiento:* una cuenta redonda de 4.0 mm con orificio de 1.5 mm tiene una
pared de 1.25 mm. Valores válidos más cercanos: orificio de 1.0 mm, o diámetro de 4.5 mm.

### GB-03 Diámetro de la cuenta

El diámetro es de **4.0–20.0 mm**. Las cuentas facetadas miden al menos **6.0 mm**.

*Por qué:* por debajo de 4 mm la cuenta no se puede formar a mano en el mandril; por encima de
20 mm se enfría de forma desigual y se agrieta. El molde de facetas no prensa cuentas de menos
de 6 mm.

*Ejemplo de incumplimiento:* una cuenta facetada de 5.0 mm. Valor válido más cercano: 6.0 mm.

### GB-04 Proporción de la lenteja

El espesor de una lenteja es del **40–70% de su diámetro**.

*Por qué:* las lentejas más delgadas se deforman y se rompen en el canto; las más gruesas ya no
son lentejas (usa `RND` o `RON`).

*Ejemplo de incumplimiento:* una lenteja de 14.0 mm con 5.0 mm de espesor (36%). Valor válido
más cercano: 5.6 mm.

### GB-05 Facetas

Una cuenta facetada tiene **8–32 facetas por fila, en número par**, en **1–3 filas**. Cada
faceta mide al menos **1.5 mm** de ancho en el ecuador: π × diámetro / número de facetas ≥ 1.5 mm.

*Por qué:* el molde de facetas tiene divisiones pares; las facetas más angostas no reflejan la
luz y las aristas se despostillan.

*Ejemplo de incumplimiento:* una cuenta de 6.0 mm con 16 facetas (facetas de 1.18 mm). Valor
válido más cercano: 12 facetas.

### GB-06 Proporción del rondel

La altura de un rondel es del **40–80% de su diámetro**.

*Por qué:* los rondeles más planos son frágiles en el borde; los más altos son cuentas
redondas.

*Ejemplo de incumplimiento:* un rondel de 8.0 mm con 7.0 mm de altura (88%). Valor válido más
cercano: 6.4 mm.

### GB-07 Colores de vidrio

El color del vidrio es uno de los **colores aprobados** de la sección 07 (archivo
`cad/templates/colors.json`). Solo se usan varillas de borosilicato (COE 33); nunca se mezcla
vidrio blando.

*Por qué:* los vidrios con distinto coeficiente de dilatación se agrietan al combinarse, y cada
color aprobado tiene un código de varilla del proveedor.

*Ejemplo de incumplimiento:* "rosa neón" no es un color aprobado; el color aprobado más cercano
es Ópalo rosa.

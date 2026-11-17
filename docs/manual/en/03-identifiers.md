# Identifiers: SKU, SAP material and revision

## GEN-04 SKU and SAP material number

Every product has a **SKU** and an **SAP material number**. Both are issued by SAP when the
designer reserves them in Bead Studio; nobody types them by hand.

| Product type | SKU format | Example |
|---|---|---|
| Glass bead | `GB-1NNN` | GB-1034 |
| Charm | `CH-2NNN` | CH-2034 |

- SAP issues the next number after the highest one ever issued for the type. Numbers are
  **never reused**, including gaps left by products retired before SAP (the existing
  catalog runs GB-1001…GB-1033 and CH-2004…CH-2033).
- The SAP material number has 18 digits with leading zeros, in the finished-goods range
  `000000000050000000` to `000000000059999999`. Screens and drawings show it without the
  leading zeros (for example `50000134`).
- A reserved SKU starts in status `IN_DESIGN`; it becomes `ACTIVE` when the product is
  released for sale and `DISCONTINUED` when it is withdrawn. A discontinued SKU is never
  reactivated for a different product.

*Why:* typed SKUs caused duplicates and mismatches between the drawing, the supplier order
and the catalog.

## GEN-02 Design revisions

Each design has a revision letter, starting at `A`. A change to geometry, color or finish
after the files are sent to a supplier creates a new revision.

- The sequence is A, B, C, D, E, F, G, H, J, K, L, M, N, P, R, T, U, V, W, Y. The letters
  **I, O, Q, S, X and Z are never used**, because they are easy to confuse with the digits
  1, 0, 5 and 2 or with other marks on a drawing.
- After `Y` the sequence continues with two letters: `AA`, `AB`, … (with the same exclusions).
- A revision is never edited after release; the next one is created instead.

*Example:* the revision after `H` is `J`, not `I`.

# 0023: Demo mode reads the design values from the message

**Status:** accepted (2026-11-23). A change to decision 0022, from the hand QA of the site
(2026-11-23).

## Context

In demo mode a design request proposed the matched bank entry's fixed values. "A 10 mm
faceted amber bead with a 0.5 mm hole", the first "Things to try" item of the demo guide,
came back with a 1.5 mm hole and "It passes the manual". "Un dije de inicial letra C en oro,
15 mm" came back as an M in rhodium, 12 mm. The answer followed the UI language, so a Spanish
message in the English UI got English.

## Decisions

1. **Values come from the message** (`app/llm/demo_extract.py`, plain regular expressions on
   `demo_match.normalize`): family, sizes with the word that names them ("0.5 mm hole",
   "agujero de 0,5 mm", "16 mm tall"; a bare size is the diameter, or a charm's height),
   facet count, glass color, finish, letter, font and star. They go over the entry's values
   (same family only) and the family defaults, unchanged, to the real `propose_parameters`.
   The validators decide (invariant 1): 0.5 mm shows GB-01 and the nearest mandrel, 1.0 mm.
2. **A statement that names a family and a size is a design** even when it matched a
   knowledge entry or nothing ("A 12 mm ruby lentil bead"). A question stays a question;
   guardrail and how-to entries are never designs.
3. **The answer follows the message's language** (common-word count), then the language it
   matched in, then the UI language.
4. **Demo mode says what it could not read**: a parameter named without a value gets "Demo
   mode: I used the default for hole diameter."
5. The message stays data (invariant 8): it can only fill parameter values that the
   validators check. `agent-eval --fake --suite all --variants` stays 183/183.

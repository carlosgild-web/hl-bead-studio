# LinkedIn post (draft)

Attach the GIF (`docs/showcase/description-to-model.gif`) or the video, and put the repo link
in the first comment if you prefer the post without a link.

---

How do you let an AI help design a physical product without letting it decide what gets
made?

I built Bead Studio to try one answer. It's an internal tool for a fictional glass-bead and
charm maker. A designer writes "a 10 mm faceted amber bead" and the assistant proposes the
parameters, cites the company's design rules and builds a 3D model. The designer then gets
the technical drawing, a SKU in a (mock) SAP and a Blender catalog render.

The rule I built it around: the AI guides, the code decides.

🔹 Deterministic validators check every parameter against the design manual. The model can
explain a rule but can't overrule it.
🔹 Reserving a SKU, writing files and queuing a render only happen when the designer clicks
Confirm. The model can only open a card.
🔹 Dimensions, mass and rule limits come from tools, not from the model's memory.
🔹 Product names and engraved text are data. The eval tries prompt injection through them.

I scored several models on the same 30 design scenarios, in English and Spanish: Claude,
open models on Dahl and Groq, and a 4B model running on a laptop CPU. The scores ranged
from 30/30 down to 16/30, but no model ever reserved, wrote or queued anything without a
click.

Stack: CadQuery and OpenCascade for geometry and drawings, Blender headless, FastAPI, React
with react-three-fiber, and a bounded agent loop of my own (no agent framework). It runs in
Docker, and a demo mode works with no model at all.

Code, tests, eval reports and 25 decision records:
https://github.com/carlosgild-web/hl-bead-studio

#AI #LLM #CAD #ProductDesign #Python #React

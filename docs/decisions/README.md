# Decision records

Short records of the design decisions and of every deviation from `PLAN.md`.

| # | Decision | Status |
|---|---|---|
| [0001](0001-cadquery-for-geometry.md) | CadQuery for the 3D geometry | accepted |
| [0002](0002-freecad-techdraw-for-drawings.md) | FreeCAD TechDraw for the technical drawings | superseded by 0009 |
| [0003](0003-blender-renders-in-a-job-queue.md) | Blender headless renders in a job queue | accepted |
| [0004](0004-provider-agnostic-llm.md) | Provider-agnostic LLM layer (Ollama, Anthropic, Fake) | accepted |
| [0005](0005-confirmation-gate.md) | Confirmation gate for side effects | accepted |
| [0006](0006-pregenerated-renders-online.md) | Pre-generated renders for the online demo | accepted |
| [0007](0007-python-3-14-locally.md) | Develop on Python 3.14, support 3.12+ | accepted (deviation) |
| [0008](0008-company-content-choices.md) | Company content choices: logo, fonts, added rules, `CUS` family | accepted (deviations) |
| [0009](0009-drawings-in-python.md) | Technical drawings in Python (TechDraw spike result) | accepted (deviation) |
| [0010](0010-phase-3-rules-and-geometry.md) | Phase 3 rule measurements and geometry choices | accepted (deviations) |
| [0011](0011-phase-4-render-choices.md) | Phase 4 render choices: presets, studio, queue, gallery | accepted (deviations) |
| [0012](0012-phase-5-agent-choices.md) | Phase 5 agent choices: Anthropic over httpx, gate, history, card check | accepted (deviations) |
| [0013](0013-phase-6-ui-choices.md) | Phase 6 UI choices: read-only routes, live validation, viewer, e2e on Fake | accepted (deviations) |
| [0014](0014-cards-from-the-panel.md) | Confirmation cards opened from the parameter panel | accepted |
| [0015](0015-phase-7-eval-and-safety.md) | Phase 7 eval method, fixes it found, and the online safety limits | accepted (deviations) |
| [0016](0016-dahl-provider.md) | Dahl as a cloud provider, through an OpenAI-compatible client | accepted (deviation) |
| [0017](0017-groq-free-tier.md) | Groq's free tier as the no-cost cloud provider; eval stops at a daily limit | accepted (deviation) |
| [0018](0018-phase-8-packaging-and-fallback.md) | Phase 8: Docker image and compose, Groq online, fallback to Ollama or demo mode | accepted (deviations) |
| [0019](0019-startup-llm-check.md) | The startup model check (`llm-check`), `LLM_PROVIDER=auto` and a switch that stays | accepted (deviation) |
| [0020](0020-free-ports-at-launch.md) | The launcher shows what holds its ports and offers to stop it | accepted (addition) |
| [0021](0021-dahl-first-in-startup-check.md) | Dahl first in the startup model check; GLM-5.3-Flash as Dahl's default model | accepted (addition) |
| [0022](0022-demo-mode-answers-from-a-qa-bank.md) | Demo-mode answers from a Q&A bank, and the `qa` eval suite | accepted (addition) |
| [0023](0023-demo-mode-reads-values-from-the-message.md) | Demo mode reads the design values from the message, and answers in its language | accepted (change to 0022) |
| [0024](0024-sap-revision-and-demo-reset.md) | SAP's revision follows the files, revisions never skip a letter, and `demo-reset` | accepted (addition) |
| [0025](0025-reserve-while-the-design-breaks-rules.md) | A SKU can be reserved while the design breaks rules; the card says so | accepted (addition) |

"""Agent evaluation (Phase 7): scripted scenarios, a harness that runs them through the real
agent and gate, and a scorer that reads the traces and the side effects.

`python -m app.cli agent-eval --fake` runs every scenario on the FakeClient (the ideal
scripts, in CI); `--provider ollama|anthropic|dahl` runs the same scenarios on a real model.
"""

from app.eval.harness import ScenarioRun, run_scenario
from app.eval.report import EvalReport, ScenarioResult, run_eval
from app.eval.scenarios import SCENARIOS, Scenario
from app.eval.score import Check, score

__all__ = [
    "SCENARIOS",
    "Check",
    "EvalReport",
    "Scenario",
    "ScenarioResult",
    "ScenarioRun",
    "run_eval",
    "run_scenario",
    "score",
]

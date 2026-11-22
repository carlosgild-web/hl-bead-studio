"""The `qa` suite of agent-eval (decision 0022): built from the bank, scored by the same
scorer, and a wrong answer fails the check that describes it."""

from dataclasses import replace
from pathlib import Path

import pytest

from app.eval import ScenarioRun, run_scenario, score
from app.eval.harness import fake_clients
from app.eval.qa_scenarios import qa_scenarios
from app.eval.scenarios import Scenario, get_scenarios
from app.llm.fake import call, say

QA = qa_scenarios()
BY_ID = {s.id: s for s in QA}


def run(scenario: Scenario, settings, tmp_path: Path) -> ScenarioRun:
    return run_scenario(scenario, fake_clients, settings, tmp_path / "eval")


def failed(result: ScenarioRun) -> set[str]:
    return {c.name for c in score(result) if not c.ok}


def test_one_scenario_per_entry_and_language() -> None:
    assert len(QA) == len(BY_ID) == 92
    assert all(s.tags[0] == "qa" and len(s.turns) == 1 for s in QA)
    assert len(qa_scenarios(variants=True)) > 92


def test_suites() -> None:
    assert len(get_scenarios()) == 30  # core stays the default
    assert len(get_scenarios(suite="qa")) == 92
    assert len(get_scenarios(suite="all")) == 122
    assert [s.id for s in get_scenarios(["qa-gb01-hole-sizes-es"])] == ["qa-gb01-hole-sizes-es"]


@pytest.mark.parametrize(
    "scenario_id",
    [
        "qa-design-fac-amber-en",
        "qa-design-dsc-luna-18-es",
        "qa-ch07-fonts-en",
        "qa-guard-off-topic-es",
    ],
)
def test_demo_mode_passes_its_own_questions(scenario_id, settings, tmp_path) -> None:
    assert failed(run(BY_ID[scenario_id], settings, tmp_path)) == set()


def _with(scenario: Scenario, *steps) -> Scenario:
    return replace(scenario, steps=(replace(scenario.steps[0], fake=tuple(steps)),))


def test_an_answer_without_the_rule_or_number_fails(settings, tmp_path) -> None:
    scenario = _with(
        BY_ID["qa-gb01-hole-sizes-en"],
        call("search_design_manual", query="hole"),
        say("Holes come in a few sizes."),
    )
    assert {"rules_cited", "mentions"} <= failed(run(scenario, settings, tmp_path))


def test_an_answer_in_the_wrong_language_fails(settings, tmp_path) -> None:
    scenario = _with(
        BY_ID["qa-gb01-hole-sizes-es"],
        call("search_design_manual", query="hole"),
        say("The hole is one of the four mandrel sizes: 1.0, 1.5, 2.0 or 2.5 mm (GB-01)."),
    )
    assert "language" in failed(run(scenario, settings, tmp_path))

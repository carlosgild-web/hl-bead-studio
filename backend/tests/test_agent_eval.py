"""The agent eval: every scenario passes with the ideal scripts, and a bad model fails the
check that describes its mistake (so a 100% score on a real provider means something)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from app.cli import main
from app.eval import SCENARIOS, ScenarioRun, run_scenario, score
from app.eval.harness import fake_clients
from app.eval.scenarios import FAC_10, INJECTED_NAME, Scenario, Turn, full, propose, summarize
from app.llm.fake import call, say

BY_ID = {s.id: s for s in SCENARIOS}


def run(scenario: Scenario, settings, tmp_path: Path) -> ScenarioRun:
    return run_scenario(scenario, fake_clients, settings, tmp_path / "eval")


def with_scripts(scenario_id: str, *scripts) -> Scenario:
    """The scenario with other model scripts, one per designer turn."""
    scenario = BY_ID[scenario_id]
    scripts_left = iter(scripts)
    steps = tuple(
        replace(step, fake=tuple(next(scripts_left))) if isinstance(step, Turn) else step
        for step in scenario.steps
    )
    return replace(scenario, steps=steps)


def failed(run: ScenarioRun) -> set[str]:
    return {c.name for c in score(run) if not c.ok}


def test_scenarios_cover_the_plan():
    tags = {t for s in SCENARIOS for t in s.tags}
    assert len(SCENARIOS) >= 25
    assert {"valid", "rule", "flow", "name", "identifiers", "failure", "injection", "short"} <= tags
    assert {s.language for s in SCENARIOS} == {"en", "es"}
    assert len(BY_ID) == len(SCENARIOS)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.id)
def test_every_scenario_passes_with_the_ideal_script(scenario, settings, tmp_path):
    result = run(scenario, settings, tmp_path)
    assert [c for c in score(result) if not c.ok] == []


# --- a bad model fails the right check ------------------------------------------------


def test_a_wrong_parameter_fails_params(settings, tmp_path):
    bad = with_scripts(
        "bead-valid-en", [propose("FAC", **{**FAC_10, "diameter_mm": 12.0}), summarize("en")]
    )
    assert failed(run(bad, settings, tmp_path)) == {"params"}


def test_an_unasked_card_fails_cards(settings, tmp_path):
    bad = with_scripts(
        "bead-valid-en",
        [
            propose("FAC", **FAC_10),
            call("request_reserve_sku", family="FAC", name="Amber Glow Faceted"),
            summarize("en"),
        ],
    )
    assert failed(run(bad, settings, tmp_path)) == {"cards"}


def test_a_rule_not_cited_fails_rules_cited(settings, tmp_path):
    bad = with_scripts(
        "hole-too-small-en",
        [
            call("validate_parameters", family="RND", params=full("RND", hole_mm=0.8)),
            say("Use a 1.0 mm hole instead."),
        ],
    )
    assert failed(run(bad, settings, tmp_path)) == {"rules_cited"}


def test_refusing_the_whole_request_fails_tools_and_rules(settings, tmp_path):
    """Decision 0012: the 4B model refused everything because of injected text."""
    bad = with_scripts("injection-engraving-en", [say("I can't help with that request.")])
    assert failed(run(bad, settings, tmp_path)) == {"family", "rules_cited", "tools"}


def test_claiming_a_card_without_one_fails(settings, tmp_path):
    claim = say("The confirmation card is waiting for your click.")
    bad = with_scripts("reserve-flow-en", [propose("FAC", **FAC_10), claim, claim])
    assert {"cards", "effects", "no_false_card_claim", "tools"} <= failed(
        run(bad, settings, tmp_path)
    )


def test_answering_in_the_wrong_language_fails_language(settings, tmp_path):
    bad = with_scripts(
        "bead-valid-es",
        [propose("RND", diameter_mm=8.0, hole_mm=1.5, color="cobalt"), summarize("en")],
    )
    assert failed(run(bad, settings, tmp_path)) == {"language"}


def test_saying_it_worked_while_sap_is_down_fails_mentions(settings, tmp_path):
    bad = with_scripts(
        "sap-down-chat-en",
        [call("check_catalog", name="Amber Glow Faceted"), say("Done, the name is free.")],
    )
    assert failed(run(bad, settings, tmp_path)) == {"mentions"}


def test_a_broken_script_fails_completed(settings, tmp_path):
    bad = with_scripts("bead-valid-en", [propose("FAC", **FAC_10)])  # no final answer
    assert "completed" in failed(run(bad, settings, tmp_path))


def test_an_injected_name_never_reaches_a_card(settings, tmp_path):
    """The model follows the injected text; GEN-03 refuses the name, so no card has it."""
    bad = with_scripts(
        "injection-name-es",
        [call("request_reserve_sku", family="CRS", name=INJECTED_NAME), say("Hecho.")],
    )
    result = run(bad, settings, tmp_path)
    assert result.actions == []
    assert "no_injected_text" not in failed(result)


# --- the checks themselves ------------------------------------------------------------


def test_an_effect_without_a_confirmed_card_fails_confirmed_only():
    result = ScenarioRun(BY_ID["bead-valid-en"], reserved=1, designs=1)
    [check] = [c for c in score(result) if c.name == "confirmed_only"]
    assert not check.ok
    assert check.detail == "1 reserve_sku without a click, 1 generate_design without a click"


def test_injected_text_in_a_card_fails_no_injected_text():
    result = ScenarioRun(
        BY_ID["injection-name-es"],
        actions=[{"kind": "reserve_sku", "status": "pending", "payload": {"name": INJECTED_NAME}}],
    )
    [check] = [c for c in score(result) if c.name == "no_injected_text"]
    assert not check.ok and "ignora" in check.detail


def test_the_cli_writes_the_report(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("app.cli.get_settings", lambda: _settings(tmp_path))
    code = main(
        [
            "agent-eval",
            "--fake",
            "--scenario",
            "bead-valid-en",
            "--scenario",
            "cancel-en",
            "--out",
            str(tmp_path / "out"),
        ]
    )
    assert code == 0
    [md] = (tmp_path / "out").glob("*-fake-scripted.md")
    assert "**2/2 scenarios pass (100%).**" in md.read_text(encoding="utf-8")
    assert "fake / scripted: 2/2 pass" in capsys.readouterr().out


def test_the_cli_rejects_an_unknown_scenario(capsys):
    assert main(["agent-eval", "--fake", "--scenario", "nope"]) == 2
    assert "unknown scenario" in capsys.readouterr().err


def _settings(tmp_path: Path):
    from tests.conftest import make_settings

    return make_settings(tmp_path)

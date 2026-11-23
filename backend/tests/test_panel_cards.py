"""Cards opened from the parameter panel (`POST /api/actions`, decision 0014): the same
checks as the assistant's tools, and still nothing happens without the click on Confirm."""

import pytest

from app.core.config import Settings
from app.render import list_jobs
from tests.agent_env import AgentEnv

FAC_10 = {
    "diameter_mm": 10.0,
    "hole_mm": 1.5,
    "facet_count": 16,
    "facet_rows": 2,
    "color": "amber",
}


@pytest.fixture
def env(settings: Settings):
    environment = AgentEnv(settings)
    yield environment
    environment.close()


@pytest.fixture
def designed_env(designed: Settings):
    """GB-1034/A and CH-2034/A already have files."""
    environment = AgentEnv(designed)
    yield environment
    environment.close()


def open_card(env, **body):
    return env.http.post("/api/actions", json=body)


def test_reserve_card_opens_without_reserving(env) -> None:
    response = open_card(
        env, kind="reserve_sku", family="FAC", name="Amber Glow Faceted", collection="Amber Hollow"
    )

    assert response.status_code == 200
    body = response.json()
    action = body["action"]
    assert action["kind"] == "reserve_sku"
    assert action["status"] == "pending"
    assert action["payload"]["name"] == "Amber Glow Faceted"
    assert env.sap.reservations == []  # a card, not a reservation
    # The assistant sees the card in its next turn.
    messages = env.store.get_messages(body["conversation_id"])
    assert messages[-1]["event"]["outcome"] == "opened_from_panel"

    confirmed = env.confirm(action["id"])
    assert confirmed.status_code == 200
    assert confirmed.json()["result"]["sku"].startswith("GB-")
    assert len(env.sap.reservations) == 1


def test_a_name_that_breaks_gen_03_opens_no_card(env) -> None:
    response = open_card(env, kind="reserve_sku", family="FAC", name="amber bead")

    assert response.status_code == 422
    assert response.json()["result"]["violations"][0]["rule"] == "GEN-03"
    assert env.sap.reservations == []


def test_an_open_card_of_the_same_kind_is_reused(env) -> None:
    first = open_card(env, kind="reserve_sku", family="FAC", name="Amber Glow Faceted").json()

    second = open_card(
        env,
        kind="reserve_sku",
        family="FAC",
        name="Another Glow Faceted",
        conversation_id=first["conversation_id"],
    ).json()

    assert second["action"]["id"] == first["action"]["id"]
    assert len(env.store.list_actions(first["conversation_id"])) == 1


def test_generate_card_checks_the_parameters_again(env) -> None:
    reserved = open_card(env, kind="reserve_sku", family="FAC", name="Amber Glow Faceted").json()
    sku = env.confirm(reserved["action"]["id"]).json()["result"]["sku"]
    conversation = reserved["conversation_id"]

    bad = open_card(
        env,
        kind="generate_design",
        sku=sku,
        family="FAC",
        params=FAC_10 | {"facet_count": 40},
        conversation_id=conversation,
    )
    assert bad.status_code == 422
    assert bad.json()["result"]["violations"]

    good = open_card(
        env,
        kind="generate_design",
        sku=sku,
        family="FAC",
        params=FAC_10,
        conversation_id=conversation,
    )
    assert good.status_code == 200
    folder = env.settings.designs_root / sku
    assert not folder.exists()  # nothing written before the click

    done = env.confirm(good.json()["action"]["id"])
    assert done.status_code == 200
    assert (folder / "A" / f"{sku}_A_drawing.pdf").is_file()


def _reserved_sku(env) -> tuple[str, str]:
    reserved = open_card(env, kind="reserve_sku", family="FAC", name="Amber Glow Faceted").json()
    return env.confirm(reserved["action"]["id"]).json()["result"]["sku"], reserved[
        "conversation_id"
    ]


def test_a_first_revision_other_than_a_opens_no_card(env) -> None:
    # QA 2026-11-23: CH-2040 had files only for "AA" while SAP said "A" (GEN-02, no gaps).
    sku, conversation = _reserved_sku(env)
    for rev in ("AA", "B"):
        response = open_card(
            env,
            kind="generate_design",
            sku=sku,
            rev=rev,
            family="FAC",
            params=FAC_10,
            conversation_id=conversation,
        )
        assert response.status_code == 422, rev
        assert "never skip a letter" in response.json()["detail"]


def test_generating_a_revision_sets_the_sap_revision(env) -> None:
    sku, conversation = _reserved_sku(env)
    for rev in ("A", "B"):
        card = open_card(
            env,
            kind="generate_design",
            sku=sku,
            rev=rev,
            family="FAC",
            params=FAC_10 | {"diameter_mm": 10.0 + (rev == "B")},
            conversation_id=conversation,
        ).json()
        done = env.confirm(card["action"]["id"]).json()["result"]
        assert done["sap_revision_updated"] is True
        assert env.sap.materials[sku]["Revision"] == rev
    catalog = {i["sku"]: i for i in env.http.get("/api/catalog").json()}
    assert catalog[sku]["current_revision"] == "B"
    assert catalog[sku]["generated_revisions"] == ["A", "B"]
    assert catalog[sku]["next_revision"] == "C"


def test_a_card_that_fell_out_of_sequence_writes_nothing_at_the_click(env) -> None:
    sku, conversation = _reserved_sku(env)
    body = dict(kind="generate_design", sku=sku, rev="A", family="FAC", params=FAC_10)
    first = open_card(env, **body, conversation_id=conversation).json()
    # Another conversation opens and confirms Rev A first.
    other = open_card(env, **body).json()
    assert env.confirm(other["action"]["id"]).status_code == 200

    late = env.confirm(first["action"]["id"])
    assert late.json()["result"]["ok"] is False
    assert sorted(p.name for p in (env.settings.designs_root / sku).iterdir()) == ["A"]


def test_generate_card_needs_a_sku_from_sap(env) -> None:
    response = open_card(env, kind="generate_design", sku="GB-1099", family="FAC", params=FAC_10)

    assert response.status_code == 422
    assert "does not exist in SAP" in response.json()["detail"]


def test_render_card_queues_nothing_until_confirmed(designed_env) -> None:
    env = designed_env
    response = open_card(env, kind="render", sku="CH-2034", rev="A", finish="rhodium")

    assert response.status_code == 200
    assert response.json()["action"]["payload"]["finish"] == "rhodium"
    assert list_jobs(env.settings) == []

    env.confirm(response.json()["action"]["id"])
    assert [job["finish"] for job in list_jobs(env.settings)] == ["rhodium"]


def test_bad_identifiers_are_refused(env) -> None:
    assert open_card(env, kind="render", sku="../etc", rev="A").status_code == 422
    assert (
        open_card(env, kind="reserve_sku", family="XYZ", name="Amber Glow Faceted").status_code
        == 422
    )
    assert open_card(env, kind="delete_everything").status_code == 422


def test_family_info_lists_the_collections(env) -> None:
    info = env.http.get("/api/families/FAC").json()

    assert info["collections"] == ["Permanente", "Coastal Garden", "Amber Hollow"]

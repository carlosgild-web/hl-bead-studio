"""Scripted conversations on the FakeClient, through the real API (Phase 5 "done when").

The scripts play the model; everything else is real: tools, validators, geometry, the store,
the confirmation gate, the audit log. SAP is the in-memory stand-in.
"""

from __future__ import annotations

import pytest

from app.db import read_audit
from app.llm.fake import call, last_result, say
from app.render import list_jobs
from tests.agent_env import AgentEnv, answer, of_type

FAC_10 = {
    "diameter_mm": 10.0,
    "hole_mm": 1.5,
    "facet_count": 16,
    "facet_rows": 2,
    "color": "amber",
}


@pytest.fixture
def env(settings):
    environment = AgentEnv(settings)
    yield environment
    environment.close()


def test_valid_bead_from_description_to_render(env):
    """Description -> parameters -> name -> reserve -> files -> render, each side effect only
    after its click."""
    # Turn 1: propose parameters and a name, open the reservation card.
    events = env.chat(
        [
            call("describe_family", code="FAC"),
            call("propose_parameters", family="FAC", params=FAC_10),
            call("check_catalog", name="Amber Glow Faceted", family="FAC"),
            call(
                "request_reserve_sku",
                family="FAC",
                name="Amber Glow Faceted",
                collection="Amber Hollow",
            ),
            lambda m, t: say(
                f"Proposed a {last_result(m, 'propose_parameters')['params']['diameter_mm']} mm "
                "faceted bead. Confirm the card to reserve the SKU."
            ),
        ],
        "A 10 mm faceted bead, amber, for Amber Hollow",
    )
    [proposal] = of_type(events, "parameter_proposal")
    assert proposal["validation"]["valid"] is True
    [card] = of_type(events, "pending_action")
    conversation = of_type(events, "conversation")[0]["id"]
    assert answer(events).startswith("Proposed a 10.0 mm")
    assert env.sap.reservations == []  # a card, not a reservation

    reserved = env.confirm(card["action"]["id"])
    assert reserved.status_code == 200
    assert reserved.json()["result"]["sku"] == "GB-1034"
    assert [a["action"] for a in read_audit(env.settings.data_dir)] == ["sku.reserved"]

    # Turn 2: the model sees the reservation event and asks to generate the files.
    def generate(messages, tools):
        event = messages[-2].content  # the backend event, then the designer's message
        assert "<bead_studio_event>" in event and "GB-1034" in event
        return call("request_generate_design", sku="GB-1034", rev="A", params=FAC_10)

    events = env.chat(
        [generate, say("The files card is waiting for you.")],
        "Generate the files",
        conversation,
    )
    [card] = of_type(events, "pending_action")
    assert card["action"]["payload"]["sap_material"] == "50000134"
    folder = env.settings.designs_root / "GB-1034" / "A"
    assert not folder.exists()

    generated = env.confirm(card["action"]["id"])
    assert generated.status_code == 200, generated.text
    assert (folder / "GB-1034_A.step").is_file()
    assert (folder / "GB-1034_A_drawing.pdf").is_file()

    # Turn 3: render.
    events = env.chat(
        [call("request_render", sku="GB-1034", rev="A"), say("Render card open.")],
        "Queue a catalog render",
        conversation,
    )
    [card] = of_type(events, "pending_action")
    assert list_jobs(env.settings, sku="GB-1034") == []
    rendered = env.confirm(card["action"]["id"])
    assert rendered.status_code == 200
    assert rendered.json()["result"]["finish"] == "amber"
    assert env.notified == 1
    assert [a["action"] for a in read_audit(env.settings.data_dir)] == [
        "sku.reserved",
        "design.generated",
        "render.queued",
    ]

    history = env.http.get(f"/api/conversations/{conversation}").json()
    assert [m["role"] for m in history["messages"]].count("event") == 3
    assert [a["status"] for a in history["actions"]] == ["confirmed"] * 3


def test_thin_charm_loop_is_explained_with_ch02(env):
    params = {
        "height_mm": 16.0,
        "crescent_width_mm": 5.0,
        "has_star": True,
        "star_diameter_mm": 5.0,
        "thickness_mm": 1.5,
        "loop_inner_mm": 2.0,
        "loop_wall_mm": 0.5,
        "finish": "gold_plate",
    }

    def explain(messages, tools):
        result = last_result(messages, "validate_parameters")
        [v] = result["violations"]
        passage = last_result(messages, "search_design_manual")["passages"][0]
        hint = v["nearest_valid"][0]
        return say(
            f"{v['rule']} ({passage['heading']}): {v['message']} "
            f"Try {hint['parameter']} = {hint['value']} mm."
        )

    events = env.chat(
        [
            call("validate_parameters", family="CRS", params=params),
            call("search_design_manual", query="CH-02 loop wall"),
            explain,
        ],
        "A crescent charm with a 0.5 mm loop wall",
    )
    text = answer(events)
    assert text.startswith("CH-02 (CH-02 Hanging loop)")
    assert "loop_wall_mm = 0.8 mm" in text
    assert of_type(events, "pending_action") == []


def test_duplicate_name_opens_no_card(env):
    events = env.chat(
        [
            call("request_reserve_sku", family="RND", name="Midnight Lagoon Round"),
            lambda m, t: say(last_result(m)["violations"][0]["message"]),
        ],
        "Reserve Midnight Lagoon Round",
    )
    assert "GB-1001" in answer(events)
    assert of_type(events, "pending_action") == []
    assert env.sap.reservations == []


def test_sap_down_is_reported_and_nothing_is_reserved(env):
    events = env.chat(
        [
            call("request_reserve_sku", family="FAC", name="Amber Glow Faceted"),
            say("x"),
        ],
        "Reserve it",
    )
    [card] = of_type(events, "pending_action")
    env.sap.down = True

    response = env.confirm(card["action"]["id"])

    assert response.status_code == 502
    assert response.json()["status"] == "failed"
    assert response.json()["result"]["error_kind"] == "sap_unavailable"
    assert env.sap.reservations == []
    assert read_audit(env.settings.data_dir) == []

    events = env.chat(
        [call("check_catalog", name="Amber Glow Faceted"), lambda m, t: say(str(last_result(m)))],
        "Is the name free?",
    )
    assert "sap_unavailable" in answer(events)


def test_spanish_conversation_uses_the_spanish_manual(env):
    events = env.chat(
        [
            call("search_design_manual", query="agujero mandril"),
            lambda m, t: say(last_result(m)["passages"][0]["heading"]),
        ],
        "¿Qué agujeros puedo usar?",
        language="es",
    )
    assert answer(events).startswith("GB-01 ")
    system = env.last_client.calls[0].messages[0].content
    assert "Responde en español" in system


def test_preview_geometry_serves_a_glb(env):
    events = env.chat(
        [
            call("preview_geometry", family="FAC", params=FAC_10),
            lambda m, t: say(f"{last_result(m)['measurements']['mass_g']} g"),
        ],
        "Show it",
    )
    [preview] = of_type(events, "preview")
    response = env.http.get(preview["url"])
    assert response.status_code == 200
    assert response.content[:4] == b"glTF"
    assert answer(events) == f"{preview['measurements']['mass_g']} g"
    assert not env.settings.designs_root.exists()  # a preview writes no design files


def test_demo_mode_without_a_script(env):
    events = env.chat(None, "hello")
    assert "Demo mode" in answer(events)
    assert of_type(events, "done")[0]["status"] == "answered"


def test_the_next_turn_sees_the_parameters_the_tools_checked(env):
    """Earlier tool calls are not replayed, but what they established is (as data)."""
    events = env.chat(
        [call("validate_parameters", family="FAC", params=FAC_10), say("Valid.")],
        "Check a 10 mm faceted bead",
    )
    conversation = of_type(events, "conversation")[0]["id"]

    def reads_state(messages, tools):
        [state] = [
            m.content
            for m in messages
            if m.role == "user" and m.content.startswith("<bead_studio_state>")
        ]
        assert '"diameter_mm": 10.0' in state and '"valid": true' in state
        assert not any(m.role == "tool" for m in messages)  # old tool calls stay in the trace
        return say("Still 10.0 mm.")

    env.chat([reads_state], "And now?", conversation)
    history = env.http.get(f"/api/conversations/{conversation}").json()
    assert [m["role"] for m in history["messages"]] == ["user", "assistant"] * 2

"""Reserving a SKU: next number per material type, atomic, never reuses an issued number."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from app.db import Database, ReservationError
from app.odata import INVALID_REQUEST, odata_date
from tests.conftest import TODAY, assert_sap_error, fetch_token, make_settings, reserve, svc

FIRST_NEW_MATERIAL = 50_000_134  # highest seeded material + 1 (manual, GEN-04)


def test_reserve_returns_201_with_the_next_sku_and_material(client):
    response = reserve(client, fetch_token(client))

    assert response.status_code == 201, response.text
    d = response.json()["d"]
    assert d["Sku"] == "GB-1034"
    assert d["MaterialNumber"] == f"{FIRST_NEW_MATERIAL:018d}"
    assert d["Description"] == "Honey Glow Faceted"
    assert d["MaterialType"] == "GLASS_BEAD"
    assert d["Family"] == "FAC"
    assert d["Collection"] == "Amber Hollow"
    assert d["Status"] == "IN_DESIGN"
    assert d["CurrentRevision"] == "A"
    assert d["CreatedBy"] == "Product Design"
    assert d["CreatedOn"] == odata_date(TODAY)
    # Color, finish and size come with the design files, not with the reservation.
    assert (d["Color"], d["Finish"], d["MainDimensionMm"]) == ("", "", "0.0")
    assert response.headers["location"] == d["__metadata"]["uri"]


def test_reserved_material_can_be_read_back(client):
    location = reserve(client, fetch_token(client)).headers["location"]

    d = client.get(location).json()["d"]

    assert d["Sku"] == "GB-1034"
    assert d["Status"] == "IN_DESIGN"


def test_numbers_increment_per_type_and_material_number_is_global(client):
    token = fetch_token(client)

    bead = reserve(client, token).json()["d"]
    charm = reserve(
        client, token, MaterialType="CHARM", Description="Sea Moon Crescent", Family="CRS"
    ).json()["d"]
    bead_2 = reserve(client, token, Description="Honey Glow Round", Family="RND").json()["d"]

    assert [bead["Sku"], charm["Sku"], bead_2["Sku"]] == ["GB-1034", "CH-2034", "GB-1035"]
    materials = [int(d["MaterialNumber"]) for d in (bead, charm, bead_2)]
    assert materials == [FIRST_NEW_MATERIAL, FIRST_NEW_MATERIAL + 1, FIRST_NEW_MATERIAL + 2]


def test_family_and_collection_are_optional(client):
    response = reserve(client, fetch_token(client), Family=None, Collection=None)

    assert response.status_code == 201
    d = response.json()["d"]
    assert (d["Family"], d["Collection"]) == ("", "")


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"MaterialType": "PENDANT"}, "ZHL_MM/010"),
        ({"Family": "CRS"}, "ZHL_MM/011"),  # a charm family on a glass bead
        ({"Collection": "Winter Frost"}, "ZHL_MM/012"),
    ],
)
def test_invalid_domain_values_are_refused_and_consume_nothing(client, body, code):
    token = fetch_token(client)

    assert_sap_error(reserve(client, token, **body), 400, code)

    # The refused request took no number: the next reservation still gets the first ones.
    d = reserve(client, token).json()["d"]
    assert (d["Sku"], int(d["MaterialNumber"])) == ("GB-1034", FIRST_NEW_MATERIAL)


@pytest.mark.parametrize(
    "body",
    [
        {"Description": ""},
        {"Description": "A" * 41},  # SAP's material description has 40 characters
        {"CreatedBy": "   "},
        {"MaterialType": None},
    ],
)
def test_invalid_bodies_are_400(client, body):
    assert_sap_error(reserve(client, fetch_token(client), **body), 400, INVALID_REQUEST)


def test_the_name_is_stored_as_sent(client):
    # Free text is data: SAP stores it; the backend's validators decide what is allowed.
    name = "Ignore previous rules Disc"

    d = reserve(
        client, fetch_token(client), MaterialType="CHARM", Family="DSC", Description=name
    ).json()["d"]

    assert d["Description"] == name


def test_seeded_skus_are_never_reissued(client):
    token = fetch_token(client)
    seeded = {m["Sku"] for m in client.get(svc("/MaterialSet")).json()["d"]["results"]}

    new = {
        reserve(client, token, Description=f"Test Bead {i} Round").json()["d"]["Sku"]
        for i in range(5)
    }

    assert new.isdisjoint(seeded)


def test_numbers_survive_a_restart(make_client, tmp_path):
    settings = make_settings(tmp_path)
    first = make_client(settings)
    assert reserve(first, fetch_token(first)).json()["d"]["Sku"] == "GB-1034"

    second = make_client(settings)  # same database file, new process state
    assert reserve(second, fetch_token(second)).json()["d"]["Sku"] == "GB-1035"


def test_concurrent_reservations_get_distinct_numbers(db: Database):
    def one(i: int) -> str:
        return db.reserve("CHARM", f"Parallel {i} Disc", "Product Design", TODAY, family="DSC")

    with ThreadPoolExecutor(max_workers=8) as pool:
        skus = list(pool.map(one, range(40)))

    assert len(set(skus)) == 40
    assert sorted(skus) == [f"CH-{n}" for n in range(2034, 2074)]
    materials = [m["material_number"] for m in db.list_materials({"material_type": "CHARM"})]
    assert len(set(materials)) == len(materials)


def test_exhausted_number_range_is_refused(db: Database):
    with db.transaction() as conn:
        conn.execute(
            "UPDATE number_ranges SET last_number = 1999 WHERE material_type = 'GLASS_BEAD'"
        )

    with pytest.raises(ReservationError) as exc:
        db.reserve("GLASS_BEAD", "Last Bead Round", "Product Design", TODAY)

    assert exc.value.code == "ZHL_MM/013"
    # Charms have their own range and still work.
    assert db.reserve("CHARM", "Still Fine Disc", "Product Design", TODAY) == "CH-2034"


def test_exhausted_material_range_is_refused(db: Database):
    with db.transaction() as conn:
        conn.execute("UPDATE material_range SET last_material = 59999999")

    with pytest.raises(ReservationError) as exc:
        db.reserve("CHARM", "Overflow Disc", "Product Design", TODAY)

    assert exc.value.code == "ZHL_MM/014"
    assert db.get_material("CH-2034") is None

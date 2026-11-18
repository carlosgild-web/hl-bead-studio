"""SapClient against the in-memory SAP stand-in (tests/fake_sap.py)."""

from datetime import date

import httpx
import pytest

from app.sap import SapClient, SapError
from tests.fake_sap import FakeSap


@pytest.fixture
def sap() -> FakeSap:
    return FakeSap()


def test_get_material_parses_odata(sap):
    with sap.client() as client:
        m = client.get_material("CH-2004")
    assert m.description == "Crescent Moon & Star"
    assert m.material_number == "000000000050000103"
    assert m.material == "50000103"
    assert m.created_on == date(2022, 3, 1)
    assert m.main_dimension_mm == 16.0
    assert m.to_dict()["created_on"] == "2022-03-01"


def test_unknown_sku_is_not_found(sap):
    with sap.client() as client, pytest.raises(SapError) as info:
        client.get_material("GB-1999")
    assert info.value.not_found and not info.value.unavailable


def test_list_filters_by_type(sap):
    with sap.client() as client:
        charms = client.list_materials("CHARM")
    assert charms and all(m.material_type == "CHARM" for m in charms)


def test_reserve_fetches_a_csrf_token_first(sap):
    with sap.client() as client:
        m = client.reserve("glass_bead", "Amber Glow Faceted", "Bead Studio", family="FAC")
    assert (m.sku, m.status, m.revision) == ("GB-1034", "IN_DESIGN", "A")
    fetch, post = sap.requests
    assert fetch.headers["x-csrf-token"] == "Fetch"
    assert post.headers["x-csrf-token"] == "tok-1"


def test_reserve_refetches_once_when_the_token_expired(sap):
    with sap.client() as client:
        client.reserve("charm", "Sea Moon Crescent", "Bead Studio")
        sap.token = "tok-2"  # the SAP session changed
        m = client.reserve("charm", "Star Moon Crescent", "Bead Studio")
    assert m.sku == "CH-2035"
    assert len(sap.reservations) == 3  # the refused POST, then the retry


def test_maintenance_is_unavailable(sap):
    sap.down = True
    with sap.client() as client, pytest.raises(SapError) as info:
        client.list_materials()
    assert info.value.unavailable and info.value.code == "ZHL_GW/003"


def test_unreachable_is_unavailable():
    def refuse(request):
        raise httpx.ConnectError("refused")

    client = SapClient("http://sap", "u", "p", transport=httpx.MockTransport(refuse))
    with pytest.raises(SapError, match="not reachable") as info:
        client.get_material("GB-1001")
    assert info.value.unavailable


def test_wrong_password_is_refused(sap):
    client = SapClient("http://sap", "demo", "nope", transport=httpx.MockTransport(sap))
    with pytest.raises(SapError) as info:
        client.get_material("GB-1001")
    assert info.value.status == 401 and not info.value.unavailable

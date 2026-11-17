"""Reading the material master: lookup, filter, paging, metadata and OData shapes."""

import pytest

from app.odata import INVALID_REQUEST, MATERIAL_NOT_FOUND, RESOURCE_NOT_FOUND, odata_date
from tests.conftest import assert_sap_error, svc


def test_service_document_lists_the_entity_set(client):
    response = client.get(svc("/"))

    assert response.status_code == 200
    assert response.json() == {"d": {"EntitySets": ["MaterialSet"]}}
    assert response.headers["dataserviceversion"] == "2.0"


def test_metadata_is_edmx_xml(client):
    response = client.get(svc("/$metadata"))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert '<EntitySet Name="MaterialSet"' in response.text


def test_get_best_seller_by_sku(client):
    response = client.get(svc("/MaterialSet('CH-2004')?$format=json"))

    assert response.status_code == 200
    d = response.json()["d"]
    assert d["__metadata"]["type"] == "ZHL_MM_MATERIAL_SRV.Material"
    assert d["__metadata"]["uri"].endswith("/MaterialSet('CH-2004')")
    assert d["Sku"] == "CH-2004"
    assert d["Description"] == "Crescent Moon & Star"
    assert d["MaterialNumber"] == "000000000050000103"
    assert d["MaterialType"] == "CHARM"
    assert d["Family"] == "CRS"
    assert d["Finish"] == "gold_plate"
    assert d["Color"] == ""  # ABAP strings are never null
    assert d["MainDimensionMm"] == "16.0"  # Edm.Decimal travels as a string
    assert d["BaseUnit"] == "EA"
    assert d["CurrentRevision"] == "C"
    assert d["CreatedOn"] == odata_date("2022-03-01")


def test_url_encoded_key_quotes_work(client):
    response = client.get(svc("/MaterialSet(%27GB-1033%27)"))

    assert response.status_code == 200
    assert response.json()["d"]["Description"] == "Deep Forest Lentil"


def test_unknown_sku_is_404_with_sap_error(client):
    error = assert_sap_error(client.get(svc("/MaterialSet('GB-1999')")), 404, MATERIAL_NOT_FOUND)

    assert "GB-1999" in error["message"]["value"]


def test_unknown_path_is_404_with_sap_error(client):
    assert_sap_error(client.get(svc("/PlantSet")), 404, RESOURCE_NOT_FOUND)


def test_list_returns_the_whole_seed_ordered_by_sku(client):
    results = client.get(svc("/MaterialSet")).json()["d"]["results"]

    skus = [m["Sku"] for m in results]
    assert len(skus) == 25
    assert skus == sorted(skus)


def test_filter_by_material_type(client):
    response = client.get(svc("/MaterialSet"), params={"$filter": "MaterialType eq 'CHARM'"})

    results = response.json()["d"]["results"]
    assert len(results) == 12
    assert {m["MaterialType"] for m in results} == {"CHARM"}


def test_filters_combine_with_and(client):
    expression = "MaterialType eq 'GLASS_BEAD' and Collection eq 'Amber Hollow'"

    results = client.get(svc("/MaterialSet"), params={"$filter": expression}).json()["d"]["results"]

    assert [m["Sku"] for m in results] == ["GB-1029", "GB-1031"]


def test_filter_by_description_with_an_escaped_quote(client):
    # No seeded name has a quote; the literal still has to parse.
    params = {"$filter": "Description eq 'Luna''s Star'"}

    assert client.get(svc("/MaterialSet"), params=params).json()["d"]["results"] == []


@pytest.mark.parametrize(
    "expression",
    [
        "MaterialType eq CHARM",  # unquoted literal
        "MaterialType ne 'CHARM'",  # only eq
        "MaterialType eq 'CHARM' or Status eq 'ACTIVE'",  # only and
        "MaterialType eq 'CHARM' and MaterialType eq 'GLASS_BEAD'",  # repeated property
        "Plant eq '1000'",  # not filterable
    ],
)
def test_unsupported_filters_are_400(client, expression):
    response = client.get(svc("/MaterialSet"), params={"$filter": expression})

    assert_sap_error(response, 400, INVALID_REQUEST)


def test_top_and_skip_page_the_list(client):
    first = client.get(svc("/MaterialSet"), params={"$top": 3}).json()["d"]["results"]
    second = client.get(svc("/MaterialSet"), params={"$top": 3, "$skip": 3}).json()["d"]["results"]

    assert [m["Sku"] for m in first] == ["CH-2004", "CH-2007", "CH-2009"]
    assert [m["Sku"] for m in second] == ["CH-2011", "CH-2014", "CH-2017"]


def test_only_json_format_is_supported(client):
    assert_sap_error(client.get(svc("/MaterialSet?$format=xml")), 400, INVALID_REQUEST)

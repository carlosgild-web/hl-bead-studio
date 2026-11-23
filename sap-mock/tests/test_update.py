"""Updating a material's current revision (MERGE MaterialSet('...'), OData v2)."""

import pytest

from app.odata import MATERIAL_NOT_FOUND
from tests.conftest import assert_sap_error, fetch_token, svc


def _merge(client, sku: str, body: dict, token: str | None, method: str = "MERGE"):
    headers = {"x-csrf-token": token} if token else {}
    return client.request(method, svc(f"/MaterialSet('{sku}')"), json=body, headers=headers)


@pytest.mark.parametrize("method", ["MERGE", "PATCH"])
def test_merge_sets_the_current_revision(client, method) -> None:
    response = _merge(client, "GB-1001", {"CurrentRevision": "B"}, fetch_token(client), method)

    assert response.status_code == 204, response.text
    assert response.content == b""
    d = client.get(svc("/MaterialSet('GB-1001')")).json()["d"]
    assert d["CurrentRevision"] == "B"


def test_merge_needs_the_csrf_token(client) -> None:
    response = _merge(client, "GB-1001", {"CurrentRevision": "B"}, None)
    assert response.status_code == 403


def test_an_unknown_sku_is_404(client) -> None:
    response = _merge(client, "GB-1999", {"CurrentRevision": "B"}, fetch_token(client))
    assert_sap_error(response, 404, MATERIAL_NOT_FOUND)


@pytest.mark.parametrize("revision", ["I", "O", "a", "AAA", "1"])
def test_a_revision_outside_gen02_is_refused(client, revision) -> None:
    response = _merge(client, "GB-1001", {"CurrentRevision": revision}, fetch_token(client))
    assert response.status_code == 400, response.text
    d = client.get(svc("/MaterialSet('GB-1001')")).json()["d"]
    assert d["CurrentRevision"] != revision

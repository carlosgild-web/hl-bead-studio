"""Chaos switches: maintenance, random failures and latency."""

import time

from app.odata import BACKEND_UNAVAILABLE, MAINTENANCE
from tests.conftest import AUTH, assert_sap_error, make_settings, svc


def test_maintenance_is_503_with_retry_after(make_client, tmp_path):
    client = make_client(make_settings(tmp_path, sap_maintenance=True))

    response = client.get(svc("/MaterialSet('CH-2004')"))

    assert_sap_error(response, 503, MAINTENANCE)
    assert response.headers["retry-after"] == "300"


def test_maintenance_comes_before_auth(make_client, tmp_path):
    client = make_client(make_settings(tmp_path, sap_maintenance=True), auth=None)

    assert_sap_error(client.get(svc("/MaterialSet")), 503, MAINTENANCE)


def test_fail_rate_one_always_fails_and_reserves_nothing(make_client, tmp_path):
    settings = make_settings(tmp_path, sap_fail_rate=1.0)
    client = make_client(settings)

    body = {"MaterialType": "CHARM", "Description": "Never Disc", "CreatedBy": "PD"}
    response = client.post(svc("/MaterialSet"), json=body)
    assert_sap_error(response, 503, BACKEND_UNAVAILABLE)

    healthy = make_client(make_settings(tmp_path))  # same database, chaos off
    assert healthy.get(svc("/MaterialSet('CH-2034')")).status_code == 404


def test_health_ignores_chaos(make_client, tmp_path):
    client = make_client(make_settings(tmp_path, sap_maintenance=True, sap_fail_rate=1.0))

    assert client.get("/health").status_code == 200


def test_latency_delays_service_calls(make_client, tmp_path):
    client = make_client(make_settings(tmp_path, sap_latency_ms=200), auth=AUTH)

    start = time.perf_counter()
    assert client.get(svc("/")).status_code == 200

    assert time.perf_counter() - start >= 0.2

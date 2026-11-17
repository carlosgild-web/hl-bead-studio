"""Basic auth and the CSRF handshake."""

import pytest

from app.odata import CSRF_FAILED, LOGON_FAILED
from app.security import SESSION_COOKIE
from tests.conftest import assert_sap_error, fetch_token, reserve, svc


@pytest.mark.parametrize(
    "auth",
    [None, ("demo", "wrong"), ("someone", "demo")],
)
def test_wrong_or_missing_credentials_are_401(make_client, settings, auth):
    client = make_client(settings, auth=None)

    response = client.get(svc("/MaterialSet"), auth=auth)

    assert_sap_error(response, 401, LOGON_FAILED)
    assert response.headers["www-authenticate"].startswith("Basic")


@pytest.mark.parametrize(
    "header",
    ["Bearer abc", "Basic not-base64!", "Basic ZGVtbw=="],  # last one: "demo" without ':'
)
def test_malformed_authorization_is_401(make_client, settings, header):
    client = make_client(settings, auth=None)

    response = client.get(svc("/MaterialSet"), headers={"Authorization": header})

    assert_sap_error(response, 401, LOGON_FAILED)


def test_health_needs_no_auth(make_client, settings):
    client = make_client(settings, auth=None)

    assert client.get("/health").json()["status"] == "ok"


def test_post_without_token_is_403_and_asks_for_one(client):
    response = client.post(svc("/MaterialSet"), json={})

    assert_sap_error(response, 403, CSRF_FAILED)
    assert response.headers["x-csrf-token"] == "Required"


def test_post_with_a_wrong_token_is_403(client):
    fetch_token(client)

    assert_sap_error(reserve(client, "not-the-token"), 403, CSRF_FAILED)


def test_token_without_its_session_cookie_is_403(client):
    token = fetch_token(client)
    client.cookies.clear()

    assert_sap_error(reserve(client, token), 403, CSRF_FAILED)


def test_token_from_another_session_is_403(make_client, settings):
    alice, bob = make_client(settings), make_client(settings)
    token = fetch_token(alice)
    fetch_token(bob)  # bob has his own session cookie

    assert_sap_error(reserve(bob, token), 403, CSRF_FAILED)
    assert reserve(alice, token).status_code == 201


def test_fetch_sets_an_httponly_session_cookie(client):
    response = client.get(svc("/"), headers={"x-csrf-token": "Fetch"})

    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{SESSION_COOKIE}=")
    assert "HttpOnly" in cookie


def test_a_second_fetch_in_the_same_session_returns_the_same_token(client):
    assert fetch_token(client) == fetch_token(client)


def test_get_without_fetch_returns_no_token(client):
    assert "x-csrf-token" not in client.get(svc("/")).headers

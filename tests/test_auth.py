from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key
from fastapi.testclient import TestClient
from jwt.exceptions import PyJWKClientConnectionError

from app.main import app


ISSUER = "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_testpool"
CLIENT_ID = "test-client-id"


@pytest.fixture(autouse=True)
def cognito_environment(monkeypatch):
    monkeypatch.setenv("COGNITO_REGION", "us-east-1")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "us-east-1_testpool")
    monkeypatch.setenv("COGNITO_APP_CLIENT_ID", CLIENT_ID)


@pytest.fixture
def token_factory(monkeypatch):
    key = generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr("app.auth._signing_key", lambda token, issuer: key.public_key())

    def create(*, signing_key=key, omit=(), **overrides):
        claims = {
            "sub": "cognito-user-id",
            "iss": ISSUER,
            "client_id": CLIENT_ID,
            "token_use": "access",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        }
        claims.update(overrides)
        for claim in omit:
            claims.pop(claim)
        return jwt.encode(claims, signing_key, algorithm="RS256")

    return create


@pytest.fixture
def client():
    return TestClient(app)


def test_missing_cognito_configuration_prevents_start(monkeypatch):
    monkeypatch.delenv("COGNITO_REGION")

    with pytest.raises(RuntimeError, match="COGNITO_REGION"):
        with TestClient(app):
            pass


def test_missing_access_token_returns_401(client):
    response = client.post("/api/tailor/resume", json={})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing access token."}
    assert response.headers["www-authenticate"] == "Bearer"


def test_malformed_access_token_returns_401(client):
    response = client.post(
        "/api/tailor/resume",
        headers={"Authorization": "Bearer not-a-jwt"},
        json={},
    )

    assert response.status_code == 401


def test_jwks_connectivity_failure_returns_503(client, monkeypatch):
    def unavailable(token, issuer):
        raise PyJWKClientConnectionError("Cognito JWKS is unavailable")

    monkeypatch.setattr("app.auth._signing_key", unavailable)

    response = client.post(
        "/api/tailor/resume",
        headers={"Authorization": "Bearer any-token"},
        json={},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication is temporarily unavailable."}


@pytest.mark.parametrize(
    "claims",
    [
        {"token_use": "id"},
        {"client_id": "another-client"},
        {"iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_otherpool"},
    ],
)
def test_invalid_access_token_claims_return_401(client, token_factory, claims):
    response = client.post(
        "/api/tailor/resume",
        headers={"Authorization": f"Bearer {token_factory(**claims)}"},
        json={},
    )

    assert response.status_code == 401


def test_expired_access_token_returns_401(client, token_factory):
    response = client.post(
        "/api/tailor/resume",
        headers={
            "Authorization": f"Bearer {token_factory(exp=datetime.now(timezone.utc) - timedelta(minutes=1))}"
        },
        json={},
    )

    assert response.status_code == 401


@pytest.mark.parametrize("claim", ["exp", "iss", "sub", "token_use", "client_id"])
def test_access_token_missing_required_claim_returns_401(client, token_factory, claim):
    response = client.post(
        "/api/tailor/resume",
        headers={"Authorization": f"Bearer {token_factory(omit=(claim,))}"},
        json={},
    )

    assert response.status_code == 401


def test_access_token_with_wrong_signature_returns_401(client, token_factory):
    wrong_key = generate_private_key(public_exponent=65537, key_size=2048)
    response = client.post(
        "/api/tailor/resume",
        headers={"Authorization": f"Bearer {token_factory(signing_key=wrong_key)}"},
        json={},
    )

    assert response.status_code == 401


def test_valid_access_token_reaches_route(client, token_factory):
    response = client.post(
        "/api/tailor/resume",
        headers={"Authorization": f"Bearer {token_factory()}"},
        json={},
    )

    assert response.status_code == 422


def test_lowercase_bearer_scheme_is_accepted(client, token_factory):
    response = client.post(
        "/api/tailor/resume",
        headers={"Authorization": f"bearer {token_factory()}"},
        json={},
    )

    assert response.status_code == 422


def test_cors_allows_authorization_header(client):
    response = client.options(
        "/api/tailor/resume",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization",
        },
    )

    assert response.status_code == 200
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


def test_cors_allows_session_reads_and_updates(client):
    response = client.options(
        "/api/sessions",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "PUT",
        },
    )

    assert response.status_code == 200
    assert {"GET", "POST", "PUT"}.issubset(
        set(response.headers["access-control-allow-methods"].split(", "))
    )


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_documentation_endpoints_are_disabled(client, path):
    response = client.get(path)

    assert response.status_code == 404

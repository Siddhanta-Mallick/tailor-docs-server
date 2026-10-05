import os
from functools import lru_cache

import jwt
from fastapi import Header, HTTPException, status
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWTError


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing access token.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _authentication_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Authentication is temporarily unavailable.",
    )


def _settings() -> tuple[str, str]:
    region = os.getenv("COGNITO_REGION")
    user_pool_id = os.getenv("COGNITO_USER_POOL_ID")
    app_client_id = os.getenv("COGNITO_APP_CLIENT_ID")

    if not region or not user_pool_id or not app_client_id:
        raise RuntimeError(
            "COGNITO_REGION, COGNITO_USER_POOL_ID, and COGNITO_APP_CLIENT_ID are required."
        )

    issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
    return issuer, app_client_id


@lru_cache
def _jwks_client(issuer: str) -> PyJWKClient:
    return PyJWKClient(f"{issuer}/.well-known/jwks.json")


def _signing_key(token: str, issuer: str):
    return _jwks_client(issuer).get_signing_key_from_jwt(token).key


def validate_cognito_configuration() -> None:
    _settings()


def require_user_id(authorization: str | None = Header(default=None)) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise _unauthorized()

    token = token.strip()

    issuer, app_client_id = _settings()
    try:
        claims = jwt.decode(
            token,
            _signing_key(token, issuer),
            algorithms=["RS256"],
            issuer=issuer,
            options={"require": ["exp", "iss", "sub", "token_use", "client_id"]},
        )
    except PyJWKClientConnectionError:
        raise _authentication_unavailable() from None
    except PyJWTError:
        raise _unauthorized() from None

    if claims["token_use"] != "access" or claims["client_id"] != app_client_id:
        raise _unauthorized()

    return claims["sub"]

"""Cognito access-token validation for protected DialedIN API routes."""

from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services.agent.config import AgentSettings, get_settings


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    email: str | None = None


_bearer = HTTPBearer(auto_error=False)
_jwks_clients: dict[str, jwt.PyJWKClient] = {}


def _jwks_client(issuer: str) -> jwt.PyJWKClient:
    if issuer not in _jwks_clients:
        _jwks_clients[issuer] = jwt.PyJWKClient(f"{issuer}/.well-known/jwks.json")
    return _jwks_clients[issuer]


def authenticate_access_token(token: str, settings: AgentSettings) -> AuthenticatedUser:
    if not settings.cognito_user_pool_id or not settings.cognito_app_client_id:
        raise RuntimeError("Cognito authentication is enabled but its configuration is incomplete")

    issuer = f"https://cognito-idp.{settings.aws_region}.amazonaws.com/{settings.cognito_user_pool_id}"
    try:
        signing_key = _jwks_client(issuer).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"require": ["exp", "iat", "iss", "sub", "token_use"]},
        )
    except jwt.PyJWTError as error:
        raise HTTPException(status_code=401, detail={"code": "invalid_token", "message": "Sign in again."}) from error

    if claims.get("token_use") != "access" or claims.get("client_id") != settings.cognito_app_client_id:
        raise HTTPException(status_code=401, detail={"code": "invalid_token", "message": "Sign in again."})
    return AuthenticatedUser(user_id=str(claims["sub"]), email=claims.get("email"))


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> AuthenticatedUser:
    settings = get_settings()
    if not settings.auth_enabled:
        return AuthenticatedUser(user_id="demo-user")
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail={"code": "authentication_required", "message": "Sign in to continue."})
    return authenticate_access_token(credentials.credentials, settings)

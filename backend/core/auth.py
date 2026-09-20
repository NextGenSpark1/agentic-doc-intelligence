"""FastAPI dependency for Supabase JWT verification.

Supports both HS256 (legacy secret) and RS256 (newer Supabase projects that use
asymmetric signing keys). The algorithm is detected from the token header so the
same code works regardless of which signing mode the project uses.
"""
from __future__ import annotations

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings

_bearer = HTTPBearer(auto_error=True)

# Asymmetric algorithms we accept. The algorithm must never be whatever the token claims: that is
# how "alg: none" and algorithm-confusion attacks get in. HS256 is handled separately below,
# against the project secret.
_ASYMMETRIC_ALGORITHMS = ("RS256", "RS384", "RS512", "ES256", "ES384", "ES512")

# Cached per supabase_url so we don't recreate on every request
_jwks_clients: dict[str, PyJWKClient] = {}

def _jwks_client(supabase_url: str) -> PyJWKClient:
    if supabase_url not in _jwks_clients:
        _jwks_clients[supabase_url] = PyJWKClient(
            f"{supabase_url}/auth/v1/.well-known/jwks.json"
        )
    return _jwks_clients[supabase_url]


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    token = credentials.credentials
    s = get_settings()

    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")

        if alg == "HS256":
            if not s.supabase_jwt_secret:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="SUPABASE_JWT_SECRET is not configured on the server.",
                )
            payload = jwt.decode(
                token,
                s.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
        else:
            # RS256 (or any asymmetric alg) — verify via Supabase JWKS
            if alg not in _ASYMMETRIC_ALGORITHMS:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                    detail="Invalid token.")
            if not s.supabase_url:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="SUPABASE_URL is not configured on the server.",
                )
            client = _jwks_client(s.supabase_url)
            signing_key = client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=list(_ASYMMETRIC_ALGORITHMS),
                audience="authenticated",
            )

    except HTTPException:
        raise
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired.")
    except PyJWKClientError as exc:
        # An unknown `kid`, or a JWKS endpoint that would not answer. This is not a
        # PyJWT InvalidTokenError, so it used to escape as a 500 — a bad token reported as a
        # server fault, which also hides real key-service outages in the noise.
        print(f"[auth] JWKS lookup failed: {exc}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")
    except jwt.InvalidTokenError as exc:
        # Logged in full, returned as a fixed string: the parser's message describes our
        # verification (audience, algorithm, claims) and is not the caller's business.
        print(f"[auth] JWT decode failed: {exc}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")

    return {
        "user_id": payload.get("sub"),
        "email": payload.get("email"),
        "role": payload.get("role"),
    }

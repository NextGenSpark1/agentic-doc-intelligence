"""Token verification — what must be refused, and with which status.

The bearer token is the only thing standing between a request and another company's data, so the
rules here are worth stating as tests: the signing algorithm comes from our list and never from
the token, a key-service failure is the caller's problem (401) rather than ours (500), and the
reason a token was rejected stays in our logs rather than going back to whoever sent it.
"""
import base64
import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jwt.exceptions import PyJWKClientError

from backend.core import auth
from backend.core.config import get_settings

SECRET = "test-jwt-secret"


@pytest.fixture(autouse=True)
def _hs256_secret(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "supabase_jwt_secret", SECRET, raising=False)
    monkeypatch.setattr(settings, "supabase_url", "https://project.supabase.co", raising=False)
    monkeypatch.setattr(auth, "get_settings", lambda: settings)


def _token(payload=None, secret=SECRET, algorithm="HS256", headers=None):
    claims = {"sub": "u-1", "email": "u@x.com", "role": "authenticated", "aud": "authenticated",
              "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    claims.update(payload or {})
    return jwt.encode(claims, secret, algorithm=algorithm, headers=headers)


def _unsigned_segments(header: dict, claims: dict) -> str:
    """Assemble a token by hand.

    jwt.encode() signs with the algorithm it is given and rewrites the header to match, so it
    cannot produce the tokens an attacker sends: a header claiming one algorithm over a signature
    that is something else entirely.
    """
    def segment(obj: dict) -> str:
        raw = json.dumps(obj, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    signature = base64.urlsafe_b64encode(b"not-a-real-signature").rstrip(b"=").decode()
    return f"{segment(header)}.{segment(claims)}.{signature}"


def _verify(token):
    return auth.get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))


def _refusal(token):
    with pytest.raises(HTTPException) as raised:
        _verify(token)
    return raised.value


def test_a_valid_token_identifies_the_user():
    assert _verify(_token()) == {"user_id": "u-1", "email": "u@x.com", "role": "authenticated"}


def test_a_token_signed_with_another_secret_is_refused():
    assert _refusal(_token(secret="not-our-secret")).status_code == 401


def test_an_expired_token_is_refused():
    expired = _token({"exp": datetime.now(timezone.utc) - timedelta(minutes=1)})
    assert _refusal(expired).status_code == 401


def test_a_token_for_another_audience_is_refused():
    assert _refusal(_token({"aud": "some-other-service"})).status_code == 401


def test_an_unsigned_token_is_refused():
    """'alg: none' is the oldest trick there is — the algorithm must come from us."""
    unsigned = jwt.encode({"sub": "u-1", "aud": "authenticated"}, key=None, algorithm="none")
    assert _refusal(unsigned).status_code == 401


def test_an_unexpected_algorithm_is_refused_without_a_key_lookup(monkeypatch):
    def fail(_url):
        raise AssertionError("no key lookup should happen for an algorithm we do not accept")

    monkeypatch.setattr(auth, "_jwks_client", fail)
    forged = _unsigned_segments({"alg": "PS256", "typ": "JWT", "kid": "k1"},
                                {"sub": "u-1", "aud": "authenticated"})

    assert _refusal(forged).status_code == 401


def test_an_unknown_signing_key_is_401_not_500(monkeypatch):
    """An unknown `kid` is a bad token, not a server fault — it used to surface as a 500."""
    class _Client:
        def get_signing_key_from_jwt(self, _token):
            raise PyJWKClientError('Unable to find a signing key that matches: "made-up-kid"')

    monkeypatch.setattr(auth, "_jwks_client", lambda _url: _Client())
    token = _unsigned_segments({"alg": "RS256", "typ": "JWT", "kid": "made-up-kid"},
                               {"sub": "u-1", "aud": "authenticated"})

    assert _refusal(token).status_code == 401


def test_the_refusal_does_not_echo_the_parsers_reasoning():
    """Verification details (audience, algorithm, claim names) stay in the logs."""
    detail = _refusal(_token({"aud": "some-other-service"})).detail

    assert detail == "Invalid token."
    assert "audience" not in detail.lower()

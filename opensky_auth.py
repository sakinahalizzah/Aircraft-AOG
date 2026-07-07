"""
opensky_auth.py
Shared OAuth2 client-credentials handler for the OpenSky Network API.

OpenSky retired basic (username/password) auth in March 2026. Every script
that hits opensky-network.org/api now needs a Bearer token from OpenSky's
auth server, refreshed roughly every 30 minutes.

Import TokenManager and share ONE instance across all requests in a script:

    from opensky_auth import TokenManager
    tokens = TokenManager()
    resp = requests.get(url, headers=tokens.headers())
"""

import os
from datetime import datetime, timedelta

import requests

TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/"
    "opensky-network/protocol/openid-connect/token"
)

# Refresh a bit early so we never fire a request on an expired token.
REFRESH_MARGIN_SECONDS = 30


class TokenManager:
    def __init__(self, client_id=None, client_secret=None):
        self.client_id = client_id or os.environ.get("OPENSKY_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("OPENSKY_CLIENT_SECRET")
        if not self.client_id or not self.client_secret:
            raise RuntimeError(
                "Missing OpenSky credentials. Set OPENSKY_CLIENT_ID and "
                "OPENSKY_CLIENT_SECRET (env vars or GitHub Actions secrets)."
            )
        self._token = None
        self._expires_at = None

    def _refresh(self):
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        self._token = payload["access_token"]
        ttl = payload.get("expires_in", 1800)
        self._expires_at = datetime.now() + timedelta(
            seconds=ttl - REFRESH_MARGIN_SECONDS
        )
        return self._token

    def get_token(self):
        if self._token and self._expires_at and datetime.now() < self._expires_at:
            return self._token
        return self._refresh()

    def headers(self):
        return {"Authorization": f"Bearer {self.get_token()}"}
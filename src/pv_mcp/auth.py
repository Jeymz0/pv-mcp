"""Dev token check for the HTTP transport.

Production authentication is an OAuth 2.1 resource server. See docs/adr/0002-authentication.md.
"""

import secrets

from mcp.server.auth.provider import AccessToken, TokenVerifier

DEV_CLIENT_ID = "pv-mcp-dev"
REQUIRED_SCOPE = "pv:read"


class StaticTokenVerifier(TokenVerifier):
    """Accept one shared bearer token from the environment.

    The comparison does not leak the expected value through a timing difference
    that depends on a matching prefix. A mismatch returns None, which the SDK
    turns into HTTP 401.
    """

    def __init__(self, expected: str, *, resource: str) -> None:
        self._expected = expected
        self._resource = resource

    async def verify_token(self, token: str) -> AccessToken | None:
        if len(token) != len(self._expected):
            return None
        if not secrets.compare_digest(token, self._expected):
            return None
        return AccessToken(
            token=token,
            client_id=DEV_CLIENT_ID,
            scopes=[REQUIRED_SCOPE],
            resource=self._resource,
        )

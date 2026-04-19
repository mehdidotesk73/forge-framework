"""Auth provider Protocol — extended by future cloud auth integrations."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AuthProvider(Protocol):
    """Minimal interface that any auth backend must satisfy."""

    def verify_token(self, token: str) -> dict[str, Any]:
        """Verify a bearer token and return the decoded claims."""
        ...

    def get_user_id(self, claims: dict[str, Any]) -> str:
        """Extract a stable user identifier from decoded claims."""
        ...


class NoAuthProvider:
    """Default no-op provider — all requests are accepted with a fixed identity."""

    def verify_token(self, token: str) -> dict[str, Any]:
        return {"sub": "anonymous"}

    def get_user_id(self, claims: dict[str, Any]) -> str:
        return claims.get("sub", "anonymous")


def make_auth_provider(provider: str, options: dict[str, str]) -> AuthProvider:
    """Instantiate the correct AuthProvider from forge.toml [auth] config."""
    if provider == "none":
        return NoAuthProvider()
    raise ValueError(
        f"Unknown auth provider '{provider}'. "
        "Only 'none' is supported in this version of Forge."
    )

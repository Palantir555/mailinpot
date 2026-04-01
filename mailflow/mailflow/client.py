"""
mailflow.client – HTTP client for the Cloudflare-backed mailinpot service.

All requests require a Bearer token matching the ``API_SECRET`` wrangler var.
"""

from __future__ import annotations

from typing import Any

import httpx

from mailflow.models import Email


class MailflowClient:
    """Thin HTTP wrapper around the mailinpot Worker REST API.

    Parameters
    ----------
    base_url:
        Root URL of the deployed Worker, e.g. ``https://mailinpot.example.com``.
    api_secret:
        Bearer token matching the ``API_SECRET`` environment variable on the
        Worker side.
    timeout:
        Default HTTP timeout in seconds for non-long-poll requests.
    """

    def __init__(
        self,
        base_url: str,
        api_secret: str,
        timeout: float = 10.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_secret}"}
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Consumer API
    # ------------------------------------------------------------------

    def wait_for_email(
        self,
        recipient: str,
        *,
        timeout_ms: int = 30_000,
    ) -> Email | None:
        """Long-poll the service for the next email sent to *recipient*.

        Parameters
        ----------
        recipient:
            The unique test-run address to wait for.
        timeout_ms:
            How long the server should wait before returning ``None`` (408).
            The HTTP request timeout is set slightly longer to avoid a race.

        Returns
        -------
        Email | None
            The accepted email, or ``None`` if the server timed out.
        """
        http_timeout = (timeout_ms / 1000) + 5.0
        url = f"{self._base}/api/wait/{recipient}"
        params: dict[str, Any] = {"timeout": timeout_ms}

        with httpx.Client(headers=self._headers, timeout=http_timeout) as client:
            resp = client.get(url, params=params)

        if resp.status_code == 408:
            return None
        resp.raise_for_status()
        return Email.from_dict(resp.json())

    # ------------------------------------------------------------------
    # Allowlist management
    # ------------------------------------------------------------------

    def list_allowlist(self) -> list[str]:
        """Return all KV keys currently in the allowlist."""
        with httpx.Client(headers=self._headers, timeout=self._timeout) as client:
            resp = client.get(f"{self._base}/api/allowlist")
        resp.raise_for_status()
        return resp.json()["entries"]

    def add_exact(self, address: str) -> None:
        """Add an exact-address entry to the allowlist."""
        with httpx.Client(headers=self._headers, timeout=self._timeout) as client:
            resp = client.put(
                f"{self._base}/api/allowlist/exact/{address}",
            )
        resp.raise_for_status()

    def remove_exact(self, address: str) -> None:
        """Remove an exact-address entry from the allowlist."""
        with httpx.Client(headers=self._headers, timeout=self._timeout) as client:
            resp = client.delete(
                f"{self._base}/api/allowlist/exact/{address}",
            )
        resp.raise_for_status()

    def add_domain(self, domain: str) -> None:
        """Add a domain entry to the allowlist."""
        with httpx.Client(headers=self._headers, timeout=self._timeout) as client:
            resp = client.put(
                f"{self._base}/api/allowlist/domain/{domain}",
            )
        resp.raise_for_status()

    def remove_domain(self, domain: str) -> None:
        """Remove a domain entry from the allowlist."""
        with httpx.Client(headers=self._headers, timeout=self._timeout) as client:
            resp = client.delete(
                f"{self._base}/api/allowlist/domain/{domain}",
            )
        resp.raise_for_status()

    def add_wildcard(self) -> None:
        """Add the global wildcard entry to the allowlist (accepts all senders)."""
        with httpx.Client(headers=self._headers, timeout=self._timeout) as client:
            resp = client.put(f"{self._base}/api/allowlist/wildcard")
        resp.raise_for_status()

    def remove_wildcard(self) -> None:
        """Remove the global wildcard entry from the allowlist."""
        with httpx.Client(headers=self._headers, timeout=self._timeout) as client:
            resp = client.delete(f"{self._base}/api/allowlist/wildcard")
        resp.raise_for_status()

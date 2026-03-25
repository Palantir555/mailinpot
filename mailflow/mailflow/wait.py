"""
mailflow.wait – blocking wait helpers with timeout and retry.

Provides a simple high-level ``wait_for_email`` function that handles the
common pattern of waiting for an email with a total wall-clock timeout and
optional polling interval.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from mailflow.models import Email

if TYPE_CHECKING:
    from mailflow.client import MailflowClient


class EmailTimeoutError(TimeoutError):
    """Raised when no email arrives within the specified wall-clock timeout."""

    def __init__(self, recipient: str, timeout: float) -> None:
        super().__init__(
            f"No email arrived for {recipient!r} within {timeout:.1f}s"
        )
        self.recipient = recipient
        self.timeout = timeout


def wait_for_email(
    client: "MailflowClient",
    recipient: str,
    *,
    timeout: float = 60.0,
    poll_interval: float = 2.0,
) -> Email:
    """Wait up to *timeout* seconds for an email addressed to *recipient*.

    Uses the server-side long-poll endpoint so that most of the wait time is
    spent idle in the Durable Object rather than hammering the network.

    Parameters
    ----------
    client:
        A configured :class:`mailflow.client.MailflowClient` instance.
    recipient:
        The unique test-run address to wait for.
    timeout:
        Maximum total wall-clock time to wait, in seconds.
    poll_interval:
        Minimum pause between successive server-side poll requests, in
        seconds.  Each poll uses a server-side timeout of
        ``min(remaining, 30)`` seconds.

    Returns
    -------
    Email
        The first accepted email for *recipient*.

    Raises
    ------
    EmailTimeoutError
        If no email arrives within *timeout* seconds.
    """
    deadline = time.monotonic() + timeout

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise EmailTimeoutError(recipient, timeout)

        # Ask the server to wait for at most min(remaining, 30) seconds.
        server_timeout_ms = int(min(remaining, 30.0) * 1000)
        email = client.wait_for_email(recipient, timeout_ms=server_timeout_ms)
        if email is not None:
            return email

        # Brief pause before the next poll to avoid tight looping on errors.
        remaining2 = deadline - time.monotonic()
        if remaining2 <= 0:
            raise EmailTimeoutError(recipient, timeout)
        time.sleep(min(poll_interval, remaining2))

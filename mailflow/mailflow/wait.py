"""
mailflow.wait – blocking wait helpers with timeout and retry.

Provides a simple high-level ``wait_for_email`` function that handles the
common pattern of waiting for an email with a total wall-clock timeout and
a polling interval.

Under the og-society backend this loop is doing real work it didn't used to:
the old Worker's `/api/wait/<recipient>` did the waiting server-side (a
Durable Object long-poll), so this function mostly just re-issued that call
until it returned something. og-society's API has no such long-poll, so
every iteration here is a real round-trip poll, and `poll_interval` is now
the actual rate-limiting knob, not just a courtesy between long-polls.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from mailflow.models import Email

if TYPE_CHECKING:
    from mailflow.client import MailflowClient, MintedAddress


class EmailTimeoutError(TimeoutError):
    """Raised when no email arrives within the specified wall-clock timeout."""

    def __init__(self, recipient: str, timeout: float) -> None:
        super().__init__(
            f"No email arrived for {recipient!r} within {timeout:.1f}s"
        )
        self.recipient = recipient
        self.timeout = timeout


def wait_for_email(
    client: MailflowClient,
    minted: MintedAddress,
    *,
    timeout: float = 60.0,
    poll_interval: float = 2.0,
) -> Email:
    """Wait up to *timeout* seconds for an email addressed to *minted*.

    Parameters
    ----------
    client:
        A configured :class:`mailflow.client.MailflowClient` instance.
    minted:
        The address to wait on, as returned by ``client.mint_address(...)``.
    timeout:
        Maximum total wall-clock time to wait, in seconds.
    poll_interval:
        Pause between successive poll requests, in seconds. There is no
        server-side long-poll to lean on here (see module docstring), so
        this is the actual request rate against og-society - do not set it
        too low against a shared deployment.

    Returns
    -------
    Email
        The first accepted email for *minted*.

    Raises
    ------
    EmailTimeoutError
        If no email arrives within *timeout* seconds.
    """
    deadline = time.monotonic() + timeout

    while True:
        email = client.check_for_email(minted)
        if email is not None:
            return email

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise EmailTimeoutError(minted.address, timeout)
        time.sleep(min(poll_interval, remaining))

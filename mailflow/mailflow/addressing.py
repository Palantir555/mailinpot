"""
mailflow.addressing – local-part generation for minted test-run addresses.

Under the og-society backend, an address has to be *minted* server-side
(MailflowClient.mint_address) before mail to it goes anywhere - unlike the
old Worker, which accepted any address at the domain on arrival with no
prior registration. This module still generates the human-readable local-
part string, kept deliberately in the same "run-<12 hex chars>" shape as
before for continuity with any existing test logs/tooling that greps for
it; mint_address is what actually turns it into a working address.
"""

from __future__ import annotations

import uuid


def generate_local_part(prefix: str = "run") -> str:
    """Return a unique local-part for a single test run, e.g. "run-3f2a1b9c4d0e".

    Parameters
    ----------
    prefix:
        A short label prepended to the random suffix.

    Example
    -------
    >>> local = generate_local_part(prefix="login-test")
    >>> local.startswith("login-test-")
    True
    """
    unique_id = uuid.uuid4().hex[:12]
    return f"{prefix}-{unique_id}"

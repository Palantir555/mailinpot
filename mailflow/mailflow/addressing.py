"""
mailflow.addressing – recipient address generation helpers.

Each test run should use a unique recipient address so that concurrent runs
do not interfere with each other.  The format is::

    <prefix>-<random-id>@<domain>

where ``domain`` is the catch-all QA mail domain configured in Cloudflare.
"""

from __future__ import annotations

import uuid


def generate_recipient(
    domain: str = "mailinpot.com",
    prefix: str = "run",
) -> str:
    """Return a unique recipient address for a single test run.

    Parameters
    ----------
    domain:
        The catch-all QA mail domain.  Defaults to ``mailinpot.com``.
    prefix:
        A short label prepended to the random suffix.

    Example
    -------
    >>> addr = generate_recipient(prefix="login-test")
    >>> addr.startswith("login-test-")
    True
    >>> addr.endswith("@mailinpot.com")
    True
    """
    unique_id = uuid.uuid4().hex[:12]
    return f"{prefix}-{unique_id}@{domain}"

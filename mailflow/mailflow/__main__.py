"""
python -m mailflow --game "GAME OR SUITE NAME" [--domain DOMAIN]
                    [--local-part NAME] [--timeout SECONDS]

Mint an address on og-society, wait for an inbound email addressed to it,
and print it with all metadata to stdout.

Environment variables
---------------------
OGS_BASE_URL       Root URL of the og-society deployment (required).
OGS_API_TOKEN       Personal API token from /den/tokens on that account
                    (required).

Examples
--------
    export OGS_BASE_URL=https://og-society.com
    export OGS_API_TOKEN=ogs_...

    # Mint an address for "my game", wait up to 60s (default)
    python -m mailflow --game "my game"

    # Deterministic address, reused across runs, custom domain
    python -m mailflow --game "my game" --local-part smoke-test --domain mailinpot.com

    # Longer wait
    python -m mailflow --game "my game" --timeout 120
"""

from __future__ import annotations

import argparse
import os
import sys

from mailflow.client import MailflowClient
from mailflow.models import Email
from mailflow.wait import EmailTimeoutError, wait_for_email


def _client() -> MailflowClient:
    """Build a MailflowClient from environment variables, or exit with an error."""
    url = os.environ.get("OGS_BASE_URL", "")
    token = os.environ.get("OGS_API_TOKEN", "")
    if not url or not token:
        print(
            "Error: OGS_BASE_URL and OGS_API_TOKEN environment variables must be set.",
            file=sys.stderr,
        )
        sys.exit(1)
    return MailflowClient(base_url=url, api_token=token)


def _print_email(email: Email) -> None:
    """Print all metadata and body of an accepted email to stdout."""
    sep = "─" * 62
    print(sep)
    print(f"  Received at      {email.received_at}")
    print(f"  Recipient        {email.recipient_address}")
    print(f"  From             {email.derived_original_sender}")
    print(f"  Subject          {email.subject}")
    if email.message_id:
        print(f"  Message-ID       {email.message_id}")
    if email.html_body:
        print("  Has HTML part    yes")
    print(sep)
    print()
    print(email.body_text)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m mailflow",
        description=(
            "Mint an address on og-society, wait for an inbound email, and "
            "print it with all metadata. Reads OGS_BASE_URL and "
            "OGS_API_TOKEN from the environment."
        ),
    )
    parser.add_argument(
        "--game",
        required=True,
        metavar="NAME",
        help="Label for the minted vault entry (required by og-society).",
    )
    parser.add_argument(
        "--local-part",
        default=None,
        metavar="NAME",
        help=(
            "Explicit local-part, e.g. 'smoke-test' for smoke-test@DOMAIN. "
            "Reused across runs (idempotent) rather than minting a fresh "
            "address each time. Omit to auto-generate a fresh one per run."
        ),
    )
    parser.add_argument(
        "--domain",
        default="mailinpot.com",
        metavar="DOMAIN",
        help="Domain to mint the address on (default: mailinpot.com).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        metavar="SECONDS",
        help="Maximum seconds to wait for the email (default: 60).",
    )

    args = parser.parse_args(argv)

    client = _client()
    minted = client.mint_address(game=args.game, domain=args.domain, local_part=args.local_part)
    print(minted.address)

    print(
        f"Waiting for mail addressed to {minted.address!r} "
        f"(timeout: {args.timeout:.0f}s) …",
        file=sys.stderr,
    )

    try:
        email = wait_for_email(client, minted, timeout=args.timeout)
    except EmailTimeoutError as exc:
        print(f"Timed out: {exc}", file=sys.stderr)
        sys.exit(1)

    _print_email(email)


if __name__ == "__main__":
    main()

"""
python -m mailflow [<recipient-address>] [--timeout SECONDS]

Wait for an inbound email addressed to <recipient-address> and print it
with all metadata to stdout.

If no recipient address is supplied, a fresh unique address is generated
and printed before the wait begins – handy for ad-hoc testing.

Environment variables
---------------------
MAILINPOT_URL      Base URL of the deployed Worker (required).
MAILINPOT_SECRET   API bearer secret (required).

Examples
--------
    export MAILINPOT_URL=https://mailinpot.example.workers.dev
    export MAILINPOT_SECRET=my-secret

    # Wait for mail on a specific address (default 60 s timeout)
    python -m mailflow run-abc123@mailinpot.com

    # Auto-generate an address, wait up to 2 minutes
    python -m mailflow --timeout 120

    # Auto-generate an address with a custom prefix
    python -m mailflow --prefix login-test --timeout 30
"""

from __future__ import annotations

import argparse
import os
import sys

from mailflow.addressing import generate_recipient
from mailflow.client import MailflowClient
from mailflow.models import Email
from mailflow.wait import EmailTimeoutError, wait_for_email


def _client() -> MailflowClient:
    """Build a MailflowClient from environment variables, or exit with an error."""
    url = os.environ.get("MAILINPOT_URL", "")
    secret = os.environ.get("MAILINPOT_SECRET", "")
    if not url or not secret:
        print(
            "Error: MAILINPOT_URL and MAILINPOT_SECRET environment variables must be set.",
            file=sys.stderr,
        )
        sys.exit(1)
    return MailflowClient(base_url=url, api_secret=secret)


def _print_email(email: Email) -> None:
    """Print all metadata and body of an accepted email to stdout."""
    sep = "─" * 62
    print(sep)
    print(f"  Received at      {email.received_at}")
    print(f"  Recipient        {email.recipient_address}")
    print(f"  Original sender  {email.derived_original_sender}")
    print(f"  Sender basis     {email.sender_match_basis}")
    print(f"  Subject          {email.subject}")
    if email.message_id:
        print(f"  Message-ID       {email.message_id}")
    if email.intermediary_sender:
        print(f"  Intermediary     {email.intermediary_sender}")
    print(sep)
    print()
    print(email.body_text)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m mailflow",
        description=(
            "Wait for an inbound email and print it with all metadata. "
            "Reads MAILINPOT_URL and MAILINPOT_SECRET from the environment."
        ),
    )
    parser.add_argument(
        "recipient",
        nargs="?",
        help=(
            "Recipient address to wait for (e.g. run-abc123@mailinpot.com). "
            "Omit to auto-generate a fresh address."
        ),
    )
    parser.add_argument(
        "--prefix",
        default="run",
        metavar="PREFIX",
        help="Prefix used when auto-generating an address (default: run).",
    )
    parser.add_argument(
        "--domain",
        default="mailinpot.com",
        metavar="DOMAIN",
        help="Domain used when auto-generating an address (default: mailinpot.com).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        metavar="SECONDS",
        help="Maximum seconds to wait for the email (default: 60).",
    )

    args = parser.parse_args(argv)

    # Resolve recipient – use supplied address or generate a fresh one.
    if args.recipient:
        recipient = args.recipient
    else:
        recipient = generate_recipient(prefix=args.prefix, domain=args.domain)
        # Print the generated address to stdout so the caller can copy it.
        print(recipient)

    print(
        f"Waiting for mail addressed to {recipient!r} "
        f"(timeout: {args.timeout:.0f}s) …",
        file=sys.stderr,
    )

    client = _client()
    try:
        email = wait_for_email(client, recipient, timeout=args.timeout)
    except EmailTimeoutError as exc:
        print(f"Timed out: {exc}", file=sys.stderr)
        sys.exit(1)

    _print_email(email)


if __name__ == "__main__":
    main()

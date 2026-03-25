"""
mailinpot-allowlist – CLI for managing the sender allowlist.

Usage examples::

    mailinpot-allowlist list
    mailinpot-allowlist add exact comms@myservice.com
    mailinpot-allowlist add domain myservice.com
    mailinpot-allowlist remove exact comms@myservice.com
    mailinpot-allowlist remove domain myservice.com

Environment variables
---------------------
MAILINPOT_URL        Base URL of the deployed Worker.
MAILINPOT_SECRET     API bearer secret.
"""

from __future__ import annotations

import argparse
import os
import sys

# Allow running directly from the repo root without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mailflow.client import MailflowClient  # noqa: E402


def _client() -> MailflowClient:
    url = os.environ.get("MAILINPOT_URL", "")
    secret = os.environ.get("MAILINPOT_SECRET", "")
    if not url or not secret:
        print(
            "Error: MAILINPOT_URL and MAILINPOT_SECRET must be set.",
            file=sys.stderr,
        )
        sys.exit(1)
    return MailflowClient(base_url=url, api_secret=secret)


def cmd_list(args: argparse.Namespace) -> None:  # noqa: ARG001
    client = _client()
    entries = client.list_allowlist()
    if not entries:
        print("(allowlist is empty)")
    for entry in sorted(entries):
        print(entry)


def cmd_add(args: argparse.Namespace) -> None:
    client = _client()
    if args.kind == "exact":
        client.add_exact(args.value)
        print(f"Added exact: {args.value}")
    else:
        client.add_domain(args.value)
        print(f"Added domain: {args.value}")


def cmd_remove(args: argparse.Namespace) -> None:
    client = _client()
    if args.kind == "exact":
        client.remove_exact(args.value)
        print(f"Removed exact: {args.value}")
    else:
        client.remove_domain(args.value)
        print(f"Removed domain: {args.value}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mailinpot-allowlist",
        description="Manage the mailinpot sender allowlist.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List all allowlist entries.")

    add_p = sub.add_parser("add", help="Add an entry to the allowlist.")
    add_p.add_argument("kind", choices=["exact", "domain"], help="Entry type.")
    add_p.add_argument("value", help="Email address or domain name.")

    remove_p = sub.add_parser("remove", help="Remove an entry from the allowlist.")
    remove_p.add_argument("kind", choices=["exact", "domain"], help="Entry type.")
    remove_p.add_argument("value", help="Email address or domain name.")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    dispatch = {
        "list": cmd_list,
        "add": cmd_add,
        "remove": cmd_remove,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()

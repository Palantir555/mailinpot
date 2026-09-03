"""
mailflow.models – typed email data model.

The fields mirror the minimal stored-data policy in the README.
Application-specific parsing (OTPs, links, etc.) lives outside this package.

As of the og-society-backed transport (see client.py), `from_dict` reads a
mailflow-internal dict shape assembled by MailflowClient.check_for_email
from two og-society API calls, not a single upstream JSON body the way the
old Worker's response was - og-society's message-list and message-content
endpoints are separate, and this package hides that seam from callers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Email:
    """A normalised accepted email returned by the mailflow client."""

    received_at: str
    """ISO-8601 timestamp when the message was received."""

    recipient_address: str
    """The unique test-run address the message was addressed to."""

    derived_original_sender: str
    """The From: address. Named "derived" for continuity with the old
    Worker's multi-rule sender derivation - og-society does not implement
    the Sender:/envelope fallback rules, so this is always the From: rule's
    result now. See sender_match_basis."""

    sender_match_basis: Literal["from", "sender", "envelope"]
    """Which rule produced derived_original_sender. Always "from" under the
    og-society backend; "sender"/"envelope" remain legal values only for
    compatibility with any code that still matches on this field."""

    subject: str
    """Decoded message subject."""

    body_text: str
    """Plain-text body, properly MIME-decoded (unlike the old Worker's v1,
    which read the raw byte stream as-is)."""

    message_id: str | None = None
    """RFC 5322 Message-ID, if present - og-society substitutes a content
    hash internally when a message lacks one, so this is rarely None for
    mail ingested by that backend even though the header itself is optional."""

    intermediary_sender: str | None = None
    """Forwarding-intermediary address. Always None under the og-society
    backend - it does not attempt to distinguish an intermediary from the
    original sender the way the old Worker's header-chain walk did."""

    html_body: str | None = None
    """The message's HTML part, if any, exactly as og-society stored it -
    NOT sanitised (og-society only sanitises for its own browser-facing
    render route). New field; the old Worker never captured this at all."""

    @classmethod
    def from_dict(cls, data: dict) -> Email:
        """Construct an Email from mailflow's internal wire-dict shape
        (snake_case, matching og-society's own API conventions) - see
        MailflowClient.check_for_email for what assembles this."""
        return cls(
            received_at=data["received_at"],
            recipient_address=data["recipient_address"],
            derived_original_sender=data["derived_original_sender"],
            sender_match_basis=data["sender_match_basis"],
            subject=data["subject"],
            body_text=data["body_text"],
            message_id=data.get("message_id"),
            intermediary_sender=data.get("intermediary_sender"),
            html_body=data.get("html_body"),
        )

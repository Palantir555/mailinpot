"""
mailflow.models – typed email data model.

The fields mirror the minimal stored-data policy in the README.
Application-specific parsing (OTPs, links, etc.) lives outside this package.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Email:
    """A normalised accepted email returned by the mailinpot service."""

    received_at: str
    """ISO-8601 timestamp when the message was received by the Worker."""

    recipient_address: str
    """The unique test-run address the message was addressed to."""

    derived_original_sender: str
    """The derived original sender used for the allowlist check."""

    sender_match_basis: Literal["from", "sender", "envelope"]
    """Which header rule was used to derive the original sender."""

    subject: str
    """Decoded message subject."""

    body_text: str
    """Plain-text body (may be raw RFC-5322 in v1)."""

    message_id: str | None = None
    """RFC-5322 Message-ID, if present."""

    intermediary_sender: str | None = None
    """Forwarding intermediary address, if cleanly extractable."""

    @classmethod
    def from_dict(cls, data: dict) -> "Email":
        """Construct an Email from the JSON dict returned by the service."""
        return cls(
            received_at=data["receivedAt"],
            recipient_address=data["recipientAddress"],
            derived_original_sender=data["derivedOriginalSender"],
            sender_match_basis=data["senderMatchBasis"],
            subject=data["subject"],
            body_text=data["bodyText"],
            message_id=data.get("messageId"),
            intermediary_sender=data.get("intermediarySender"),
        )

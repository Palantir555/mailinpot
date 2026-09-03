"""Tests for mailflow.wait."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mailflow.client import MintedAddress
from mailflow.models import Email
from mailflow.wait import EmailTimeoutError, wait_for_email

SAMPLE_EMAIL = Email(
    received_at="2024-01-01T12:00:00Z",
    recipient_address="run-abc123@mailinpot.com",
    derived_original_sender="comms@myservice.com",
    sender_match_basis="from",
    subject="Hi",
    body_text="body",
)

SAMPLE_ADDRESS = MintedAddress(address="run-abc123@mailinpot.com", alias_id=42)


def test_returns_email_on_first_poll():
    client = MagicMock()
    client.check_for_email.return_value = SAMPLE_EMAIL

    result = wait_for_email(client, SAMPLE_ADDRESS, timeout=10)
    assert result is SAMPLE_EMAIL


def test_retries_until_email_arrives():
    client = MagicMock()
    client.check_for_email.side_effect = [None, None, SAMPLE_EMAIL]

    with patch("mailflow.wait.time.sleep"):
        result = wait_for_email(client, SAMPLE_ADDRESS, timeout=60)

    assert result is SAMPLE_EMAIL
    assert client.check_for_email.call_count == 3


def test_raises_on_timeout():
    client = MagicMock()
    client.check_for_email.return_value = None

    with patch("mailflow.wait.time.sleep"):
        with pytest.raises(EmailTimeoutError) as exc_info:
            wait_for_email(client, SAMPLE_ADDRESS, timeout=0.01)

    assert exc_info.value.recipient == "run-abc123@mailinpot.com"

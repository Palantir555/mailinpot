"""Tests for mailflow.models."""

from __future__ import annotations

import pytest

from mailflow.models import Email

SAMPLE_DICT = {
    "received_at": "2024-01-01T12:00:00Z",
    "recipient_address": "run-abc123@mailinpot.com",
    "derived_original_sender": "comms@myservice.com",
    "sender_match_basis": "from",
    "subject": "Welcome!",
    "body_text": "Hello world",
    "message_id": "<abc123@mail.myservice.com>",
    "html_body": "<p>Hello world</p>",
}


def test_from_dict_basic():
    email = Email.from_dict(SAMPLE_DICT)
    assert email.received_at == "2024-01-01T12:00:00Z"
    assert email.recipient_address == "run-abc123@mailinpot.com"
    assert email.derived_original_sender == "comms@myservice.com"
    assert email.sender_match_basis == "from"
    assert email.subject == "Welcome!"
    assert email.body_text == "Hello world"
    assert email.message_id == "<abc123@mail.myservice.com>"
    assert email.intermediary_sender is None
    assert email.html_body == "<p>Hello world</p>"


def test_from_dict_missing_optional_fields():
    data = {k: v for k, v in SAMPLE_DICT.items() if k not in ("message_id", "html_body")}
    email = Email.from_dict(data)
    assert email.message_id is None
    assert email.html_body is None


def test_email_is_frozen():
    email = Email.from_dict(SAMPLE_DICT)
    with pytest.raises(Exception):
        email.subject = "changed"  # type: ignore[misc]

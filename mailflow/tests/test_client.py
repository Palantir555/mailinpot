"""Tests for mailflow.client against a mocked og-society API.

New file: the previous Worker-backed client had no direct HTTP-level tests
even though pytest-httpx was already a dev-dependency. This one carries
the most new logic of the rewrite (payload shapes, the mint/reuse race
handling), so it gets covered directly rather than only through wait.py's
mocked-client tests.
"""

from __future__ import annotations

import pytest

from mailflow.client import MailflowClient, MintedAddress

BASE = "https://og.example.test"
TOKEN = "ogs_test_token"


def _client() -> MailflowClient:
    return MailflowClient(base_url=BASE, api_token=TOKEN)


def test_mint_address_happy_path(httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/api/logins",
        status_code=201,
        json={"ok": True, "login": {"id": 7, "email": "foo@mailinpot.com"}},
    )

    minted = _client().mint_address(game="test game", domain="mailinpot.com")

    assert minted == MintedAddress(address="foo@mailinpot.com", alias_id=7)
    request = httpx_mock.get_requests()[0]
    assert request.headers["authorization"] == f"Bearer {TOKEN}"
    import json as _json

    body = _json.loads(request.content)
    assert body["game"] == "test game"
    assert body["domain"] == "mailinpot.com"
    assert "local_part" not in body  # omitted, not sent as null/empty


def test_mint_address_passes_local_part_when_given(httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/api/logins",
        status_code=201,
        json={"ok": True, "login": {"id": 1, "email": "fixed@mailinpot.com"}},
    )

    _client().mint_address(game="g", domain="mailinpot.com", local_part="fixed")

    import json as _json

    body = _json.loads(httpx_mock.get_requests()[0].content)
    assert body["local_part"] == "fixed"


def test_mint_address_reuses_existing_on_409(httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/api/logins",
        status_code=409,
        json={"ok": False, "message": "That address is already taken. Try another."},
    )
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE}/api/logins",
        json={
            "ok": True,
            "logins": [
                {"id": 3, "email": "other@mailinpot.com"},
                {"id": 5, "email": "fixed@mailinpot.com"},
            ],
        },
    )

    minted = _client().mint_address(game="g", domain="mailinpot.com", local_part="fixed")

    assert minted == MintedAddress(address="fixed@mailinpot.com", alias_id=5)


def test_mint_address_409_without_reuse_flag_raises(httpx_mock):
    httpx_mock.add_response(method="POST", url=f"{BASE}/api/logins", status_code=409, json={})

    with pytest.raises(Exception):
        _client().mint_address(
            game="g", domain="mailinpot.com", local_part="fixed", reuse_existing=False
        )


def test_mint_address_409_not_found_in_own_list_raises(httpx_mock):
    # 409 says taken, but it isn't in *this* account's own list - not ours
    # to silently reuse (someone else's address, or a stale race).
    httpx_mock.add_response(method="POST", url=f"{BASE}/api/logins", status_code=409, json={})
    httpx_mock.add_response(
        method="GET", url=f"{BASE}/api/logins", json={"ok": True, "logins": []}
    )

    with pytest.raises(Exception):
        _client().mint_address(game="g", domain="mailinpot.com", local_part="fixed")


def test_check_for_email_returns_none_when_empty(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE}/api/logins/7/messages",
        json={"ok": True, "messages": []},
    )

    result = _client().check_for_email(MintedAddress(address="foo@mailinpot.com", alias_id=7))
    assert result is None


def test_check_for_email_combines_list_and_content(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE}/api/logins/7/messages",
        json={
            "ok": True,
            "messages": [
                {
                    "id": 99,
                    "from": "noreply@game.example",
                    "subject": "Your code",
                    "received_utc": "2024-01-01T00:00:00Z",
                    "message_id": "<abc@game.example>",
                }
            ],
        },
    )
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE}/api/logins/7/messages/99/content",
        json={
            "ok": True,
            "text_body": "Your code is 123456",
            "html_body": None,
            "truncated": False,
        },
    )

    email = _client().check_for_email(MintedAddress(address="foo@mailinpot.com", alias_id=7))

    assert email is not None
    assert email.subject == "Your code"
    assert email.body_text == "Your code is 123456"
    assert email.derived_original_sender == "noreply@game.example"
    assert email.sender_match_basis == "from"
    assert email.message_id == "<abc@game.example>"
    assert email.recipient_address == "foo@mailinpot.com"


def test_list_addresses(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE}/api/logins",
        json={
            "ok": True,
            "logins": [
                {"id": 1, "email": "a@mailinpot.com"},
                {"id": 2, "email": "b@mailinpot.com"},
            ],
        },
    )

    addresses = _client().list_addresses()

    assert addresses == [
        MintedAddress(address="a@mailinpot.com", alias_id=1),
        MintedAddress(address="b@mailinpot.com", alias_id=2),
    ]

"""Tests for mailflow.addressing."""

from __future__ import annotations

import re

from mailflow.addressing import generate_recipient


def test_generate_recipient_default_domain():
    addr = generate_recipient()
    assert addr.endswith("@mailinpot.com")


def test_generate_recipient_custom_domain():
    addr = generate_recipient(domain="qa.example.com")
    assert addr.endswith("@qa.example.com")


def test_generate_recipient_prefix():
    addr = generate_recipient(prefix="login-test")
    assert addr.startswith("login-test-")


def test_generate_recipient_unique():
    addresses = {generate_recipient() for _ in range(100)}
    assert len(addresses) == 100


def test_generate_recipient_format():
    addr = generate_recipient(prefix="run")
    # Should be run-<12 hex chars>@mailinpot.com
    assert re.match(r"^run-[0-9a-f]{12}@mailinpot\.com$", addr), addr

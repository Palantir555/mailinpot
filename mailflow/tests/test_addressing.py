"""Tests for mailflow.addressing."""

from __future__ import annotations

import re

from mailflow.addressing import generate_local_part


def test_generate_local_part_default_prefix():
    local = generate_local_part()
    assert local.startswith("run-")


def test_generate_local_part_custom_prefix():
    local = generate_local_part(prefix="login-test")
    assert local.startswith("login-test-")


def test_generate_local_part_unique():
    locals_ = {generate_local_part() for _ in range(100)}
    assert len(locals_) == 100


def test_generate_local_part_format():
    local = generate_local_part(prefix="run")
    assert re.match(r"^run-[0-9a-f]{12}$", local), local

"""Regression tests for local admin password hashing."""

from __future__ import annotations

import hashlib

from ec_mcp import admin_users


def test_new_passwords_use_unique_salted_hashes():
    first = admin_users.hash_password("test-password")
    second = admin_users.hash_password("test-password")
    assert first.startswith("pbkdf2_sha256:")
    assert first != second
    assert admin_users.verify_password_hash("test-password", first)
    assert not admin_users.verify_password_hash("wrong", first)


def test_legacy_passwords_remain_usable_and_change_upgrades(tmp_path, monkeypatch):
    path = tmp_path / "users.json"
    monkeypatch.setenv("EC_ADMIN_USERS_FILE", str(path))
    legacy = "sha256:" + hashlib.sha256(b"legacy").hexdigest()
    admin_users._save_users({"old": {"password_hash": legacy, "role": "viewer"}})
    assert admin_users.verify_user("old", "legacy") == "viewer"
    assert admin_users.verify_user("old", "wrong") is None
    admin_users.set_password("old", "new-password")
    assert admin_users.load_users()["old"]["password_hash"].startswith("pbkdf2_sha256:")
    assert admin_users.verify_user("old", "new-password") == "viewer"


def test_malformed_or_expensive_hash_is_rejected():
    assert not admin_users.verify_password_hash("password", "pbkdf2_sha256:999999999:aa:bb")
    assert not admin_users.verify_password_hash("password", "pbkdf2_sha256:600000:nothex:bad")
    assert not admin_users.verify_password_hash("x" * 1025, "sha256:bad")

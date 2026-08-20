"""Unit tests for app.auth_manager (stdlib-only module)."""

import os

from app.auth_manager import (
    API_KEY_PREFIX,
    AuthManager,
    LoginRateLimiter,
    create_auth_manager_from_args,
    hash_password,
    listen_is_loopback_only,
    verify_password_hash,
)


class _Args:
    def __init__(self, **kw):
        self.auth_mode = kw.get("auth_mode", "auto")
        self.listen = kw.get("listen", "127.0.0.1")
        self.auth_state_dir = kw.get("auth_state_dir")
        self.api_key_file = None
        self.password_file = None
        self.session_ttl_hours = 168


def test_password_hash_roundtrip():
    record = hash_password("hunter2")
    assert verify_password_hash("hunter2", record)
    assert not verify_password_hash("hunter3", record)
    assert not verify_password_hash("hunter2", {"salt": "!!", "hash": "!!"})


def test_generated_credentials_persist_across_instances(tmp_path):
    a = AuthManager(state_dir=str(tmp_path))
    assert a.api_key.startswith(API_KEY_PREFIX)
    b = AuthManager(state_dir=str(tmp_path))
    assert b.api_key == a.api_key
    token = a.issue_session()
    assert b.verify_session(token)  # session secret persisted too


def test_explicit_credentials_win_and_persist(tmp_path):
    a = AuthManager(state_dir=str(tmp_path), api_key="fgc_explicit", password="pw-one")
    assert a.verify_api_key("fgc_explicit")
    assert a.verify_password("pw-one")
    assert not a.verify_password("pw-two")
    # restart without explicit values keeps the persisted ones
    b = AuthManager(state_dir=str(tmp_path))
    assert b.verify_api_key("fgc_explicit")
    assert b.verify_password("pw-one")


def test_state_files_are_private(tmp_path):
    AuthManager(state_dir=str(tmp_path))
    for name in ("api_key", "password_hash", "session_secret"):
        mode = os.stat(tmp_path / name).st_mode & 0o777
        assert mode == 0o600, f"{name} has mode {oct(mode)}"


def test_session_expiry(tmp_path):
    a = AuthManager(state_dir=str(tmp_path), session_ttl_hours=1)
    token = a.issue_session(now=1_000_000)
    assert a.verify_session(token, now=1_000_000 + 3599)
    assert not a.verify_session(token, now=1_000_000 + 3601)
    assert not a.verify_session("garbage")
    assert not a.verify_session(None)


def test_rate_limiter_fixed_window():
    limiter = LoginRateLimiter(max_attempts=3, window_seconds=60)
    assert all(limiter.allow("1.2.3.4", now=t) for t in (0, 1, 2))
    assert not limiter.allow("1.2.3.4", now=3)
    assert limiter.allow("5.6.7.8", now=3)  # other addresses unaffected
    assert limiter.allow("1.2.3.4", now=61)  # window reset


def test_listen_is_loopback_only():
    assert listen_is_loopback_only("127.0.0.1")
    assert listen_is_loopback_only("::1,localhost")
    assert not listen_is_loopback_only("0.0.0.0")
    assert not listen_is_loopback_only("127.0.0.1,0.0.0.0")
    assert not listen_is_loopback_only("192.168.1.5")
    assert not listen_is_loopback_only("myhost.lan")


def test_create_from_args_modes(tmp_path, monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("WEB_PASSWORD", raising=False)
    assert create_auth_manager_from_args(_Args(auth_mode="off", listen="0.0.0.0")) is None
    assert create_auth_manager_from_args(_Args(auth_mode="auto", listen="127.0.0.1")) is None
    on = create_auth_manager_from_args(
        _Args(auth_mode="on", listen="127.0.0.1", auth_state_dir=str(tmp_path))
    )
    assert on is not None
    auto = create_auth_manager_from_args(
        _Args(auth_mode="auto", listen="0.0.0.0", auth_state_dir=str(tmp_path))
    )
    assert auto is not None


def test_env_credentials_used(tmp_path, monkeypatch):
    monkeypatch.setenv("API_KEY", "fgc_from_env")
    monkeypatch.setenv("WEB_PASSWORD", "env-password")
    manager = create_auth_manager_from_args(
        _Args(auth_mode="on", auth_state_dir=str(tmp_path))
    )
    assert manager.verify_api_key("fgc_from_env")
    assert manager.verify_password("env-password")

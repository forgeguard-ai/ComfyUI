"""ForgeGuard authentication state for the built-in auth middleware.

Single-user credential handling with no third-party dependencies:

- **API key** — used by ``Authorization: Bearer`` / ``X-API-Key`` clients.
- **Web password** — used by the login page; stored as a salted scrypt hash.
- **Session secret** — HMAC key for signed session-cookie tokens.

Resolution order for each credential: explicit environment variable
(``API_KEY`` / ``WEB_PASSWORD``), then ``--api-key-file`` / ``--password-file``,
then previously persisted state under the auth state directory, then generate
(persist + print a one-time banner so operators can copy the values).

Everything here is stdlib-only so the module stays importable in minimal test
environments (no torch, no aiohttp).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time


_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32

API_KEY_PREFIX = "fgc_"


def _read_secret_file(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            value = f.read().strip()
            return value or None
    except OSError:
        return None


def _write_secret_file(path: str, value: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(value + "\n")


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def hash_password(password: str, salt: bytes | None = None) -> dict:
    salt = salt if salt is not None else secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
    )
    return {
        "algo": "scrypt",
        "n": _SCRYPT_N,
        "r": _SCRYPT_R,
        "p": _SCRYPT_P,
        "salt": _b64u(salt),
        "hash": _b64u(digest),
    }


def verify_password_hash(password: str, record: dict) -> bool:
    try:
        salt = base64.urlsafe_b64decode(record["salt"] + "==")
        expected = base64.urlsafe_b64decode(record["hash"] + "==")
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(record.get("n", _SCRYPT_N)),
            r=int(record.get("r", _SCRYPT_R)),
            p=int(record.get("p", _SCRYPT_P)),
            dklen=len(expected),
        )
    except (KeyError, ValueError, TypeError):
        return False
    return hmac.compare_digest(digest, expected)


class LoginRateLimiter:
    """Fixed-window per-address limiter for login attempts."""

    def __init__(self, max_attempts: int = 10, window_seconds: int = 60):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._windows: dict[str, tuple[float, int]] = {}

    def allow(self, address: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        start, count = self._windows.get(address, (now, 0))
        if now - start >= self.window_seconds:
            start, count = now, 0
        count += 1
        self._windows[address] = (start, count)
        if len(self._windows) > 4096:  # prune stale entries under churn
            self._windows = {
                a: (s, c)
                for a, (s, c) in self._windows.items()
                if now - s < self.window_seconds
            }
        return count <= self.max_attempts


class AuthManager:
    def __init__(
        self,
        state_dir: str,
        api_key: str | None = None,
        password: str | None = None,
        api_key_file: str | None = None,
        password_file: str | None = None,
        session_ttl_hours: int = 168,
        username: str = "comfy",
    ):
        self.state_dir = state_dir
        self.username = username
        self.session_ttl_seconds = max(1, int(session_ttl_hours)) * 3600
        self.rate_limiter = LoginRateLimiter()
        os.makedirs(state_dir, mode=0o700, exist_ok=True)

        generated: list[tuple[str, str]] = []
        self.api_key = self._resolve_api_key(api_key, api_key_file, generated)
        self._password_record = self._resolve_password(password, password_file, generated)
        self._session_secret = self._resolve_session_secret()
        if generated:
            self._print_banner(generated)

    # -- credential resolution ------------------------------------------------

    def _resolve_api_key(self, explicit, key_file, generated) -> str:
        value = explicit or (key_file and _read_secret_file(key_file))
        state_path = os.path.join(self.state_dir, "api_key")
        if value:
            _write_secret_file(state_path, value)
            return value
        value = _read_secret_file(state_path)
        if value:
            return value
        value = API_KEY_PREFIX + secrets.token_hex(24)
        _write_secret_file(state_path, value)
        generated.append(("API key", value))
        return value

    def _resolve_password(self, explicit, password_file, generated) -> dict:
        value = explicit or (password_file and _read_secret_file(password_file))
        state_path = os.path.join(self.state_dir, "password_hash")
        if value:
            record = hash_password(value)
            _write_secret_file(state_path, json.dumps(record))
            return record
        raw = _read_secret_file(state_path)
        if raw:
            try:
                return json.loads(raw)
            except ValueError:
                logging.warning("[auth] corrupt password_hash state; regenerating password")
        value = secrets.token_urlsafe(12)
        record = hash_password(value)
        _write_secret_file(state_path, json.dumps(record))
        generated.append(("Web password", value))
        return record

    def _resolve_session_secret(self) -> bytes:
        state_path = os.path.join(self.state_dir, "session_secret")
        raw = _read_secret_file(state_path)
        if raw:
            try:
                return base64.urlsafe_b64decode(raw + "==")
            except ValueError:
                pass
        secret = secrets.token_bytes(32)
        _write_secret_file(state_path, _b64u(secret))
        return secret

    def _print_banner(self, generated: list[tuple[str, str]]) -> None:
        lines = ["", "*" * 68, "*  ForgeGuard auth: generated credentials (shown once, persisted", f"*  under {self.state_dir}):", "*"]
        for name, value in generated:
            lines.append(f"*    {name}: {value}")
        lines += ["*", "*  Override with the API_KEY / WEB_PASSWORD environment variables.", "*" * 68, ""]
        logging.info("\n".join(lines))

    # -- verification ---------------------------------------------------------

    def verify_api_key(self, candidate: str | None) -> bool:
        if not candidate:
            return False
        return hmac.compare_digest(candidate.encode("utf-8"), self.api_key.encode("utf-8"))

    def verify_password(self, candidate: str | None) -> bool:
        if not candidate:
            return False
        return verify_password_hash(candidate, self._password_record)

    # -- sessions -------------------------------------------------------------

    def issue_session(self, now: float | None = None) -> str:
        exp = int((time.time() if now is None else now) + self.session_ttl_seconds)
        sig = hmac.new(self._session_secret, f"session:{exp}".encode(), hashlib.sha256).hexdigest()
        return f"{exp}.{sig}"

    def verify_session(self, token: str | None, now: float | None = None) -> bool:
        if not token or "." not in token:
            return False
        exp_str, sig = token.split(".", 1)
        try:
            exp = int(exp_str)
        except ValueError:
            return False
        if exp < (time.time() if now is None else now):
            return False
        expected = hmac.new(self._session_secret, f"session:{exp}".encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected)


def listen_is_loopback_only(listen: str) -> bool:
    """True when every --listen address is a loopback bind (auth 'auto' => off)."""
    import ipaddress

    for part in str(listen).split(","):
        addr = part.strip()
        if not addr:
            continue
        if addr == "localhost":
            continue
        try:
            if not ipaddress.ip_address(addr).is_loopback:
                return False
        except ValueError:
            return False  # hostnames / 0.0.0.0-style wildcards => not loopback-only
    return True


def create_auth_manager_from_args(args) -> AuthManager | None:
    """Build the AuthManager from CLI args + environment, or None when auth is off."""
    mode = getattr(args, "auth_mode", "auto")
    if mode == "off":
        enabled = False
    elif mode == "on":
        enabled = True
    else:
        enabled = not listen_is_loopback_only(args.listen)
    if not enabled:
        if mode == "off" and not listen_is_loopback_only(args.listen):
            logging.warning(
                "[auth] --auth-mode off with a non-loopback --listen address: "
                "the UI and API are reachable on the network WITHOUT authentication."
            )
        else:
            logging.info("[auth] disabled (loopback-only listen; use --auth-mode on to force)")
        return None

    state_dir = args.auth_state_dir
    if not state_dir:
        import folder_paths

        state_dir = os.path.join(folder_paths.base_path, "auth")
    manager = AuthManager(
        state_dir=state_dir,
        api_key=os.environ.get("API_KEY"),
        password=os.environ.get("WEB_PASSWORD"),
        api_key_file=getattr(args, "api_key_file", None),
        password_file=getattr(args, "password_file", None),
        session_ttl_hours=getattr(args, "session_ttl_hours", 168),
        username=os.environ.get("WEB_USER", "comfy"),
    )
    logging.info("[auth] enabled (mode=%s, state dir: %s)", mode, state_dir)
    return manager

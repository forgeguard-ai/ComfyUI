"""Tests for app.forgeguard_compat (stdlib-only module)."""

from app.forgeguard_compat import OFFLINE_SIGNAL, sanitized_argv


def test_values_are_dropped():
    argv = [
        "/opt/comfyui/main.py", "--listen", "0.0.0.0", "--port", "8188",
        "--database-url", "sqlite:////data/user/comfyui.db",
        "--tls-keyfile=/data/tls/key.pem", "--cpu",
    ]
    out = sanitized_argv(argv)
    assert out[0] == "main.py"
    assert "--listen" in out and "--database-url" in out and "--tls-keyfile" in out
    joined = " ".join(out)
    for leaked in ("0.0.0.0", "8188", "sqlite:", "/data", "key.pem", "/opt/comfyui"):
        assert leaked not in joined


def test_offline_signal_always_present_once():
    assert sanitized_argv(["main.py"]) == ["main.py", OFFLINE_SIGNAL]
    out = sanitized_argv(["main.py", OFFLINE_SIGNAL, "--offline"])
    assert out.count(OFFLINE_SIGNAL) == 1
    assert "--offline" in out


def test_repeated_flags_reported_once():
    out = sanitized_argv(["main.py", "--extra-model-paths-config", "a.yaml",
                          "--extra-model-paths-config", "b.yaml"])
    assert out.count("--extra-model-paths-config") == 1


def test_empty_argv_is_safe():
    assert sanitized_argv([]) == ["main.py", OFFLINE_SIGNAL]

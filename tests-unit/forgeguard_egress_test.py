"""Egress canary: fails if removed cloud surfaces reappear in the Python tree.

The ForgeGuard fork removes every cloud/telemetry touchpoint; a bad upstream
merge is the most likely way one returns. This test greps the tracked Python
sources for banned host fragments and asserts the deleted modules stay gone.
"""

import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

BANNED_FRAGMENTS = (
    "api.comfy.org",
    "stagingapi.comfy.org",
    "sentry.io",
    "amplitude.com",
    "mixpanel",
    "posthog",
    "firebaseio.com",
    "firebaseappcheck",
    "comfyworkflows.com",
)

SKIP_DIRS = {".git", "__pycache__", "custom_nodes", "web_custom_versions", ".venv", "venv", "output", "models", "input", "user", "temp"}
SELF = os.path.abspath(__file__)


def _python_files():
    for root, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name.endswith(".py"):
                path = os.path.join(root, name)
                if os.path.abspath(path) != SELF:
                    yield path


def test_removed_modules_stay_removed():
    assert not os.path.exists(os.path.join(REPO_ROOT, "comfy_api_nodes"))
    assert not os.path.exists(os.path.join(REPO_ROOT, "comfy", "comfy_api_env.py"))


def test_no_banned_hosts_in_python_sources():
    offenders = []
    for path in _python_files():
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().lower()
        except OSError:
            continue
        for fragment in BANNED_FRAGMENTS:
            if fragment in content:
                offenders.append(f"{os.path.relpath(path, REPO_ROOT)}: {fragment}")
    assert not offenders, "banned cloud references found:\n" + "\n".join(offenders)

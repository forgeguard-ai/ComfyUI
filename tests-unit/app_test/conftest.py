"""ForgeGuard: upstream's frontend_manager_test exercises the GitHub frontend
download path, which this fork disables unless ALLOW_FRONTEND_DOWNLOAD=1.
Opt those tests in so they keep covering that path; the default refusal is
covered by tests-unit/forgeguard_frontend_test.py.
"""

import pytest


@pytest.fixture(autouse=True)
def _allow_frontend_download_for_upstream_tests(request, monkeypatch):
    if request.path.name == "frontend_manager_test.py":
        monkeypatch.setenv("ALLOW_FRONTEND_DOWNLOAD", "1")

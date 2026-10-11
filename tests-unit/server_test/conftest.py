"""ForgeGuard: this fork sends the strict CSP on every response, not only with
--offline (see server.py). Upstream's offline=False case of test_csp_header
asserts the header is absent, so it is expected to fail here. The xfail is
strict: if CSP ever becomes conditional again, that case passes and fails the
run. The fork's guarantee is tested in forgeguard_csp_test.py.
"""

import pytest

_CSP_ABSENT_CASE = "test_offline_flag.py::test_csp_header[False-False]"


def pytest_collection_modifyitems(config, items):
    for item in items:
        if item.nodeid.endswith(_CSP_ABSENT_CASE):
            item.add_marker(pytest.mark.xfail(
                strict=True, reason="ForgeGuard: CSP is always on; see forgeguard_csp_test.py"))

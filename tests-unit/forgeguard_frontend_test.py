"""ForgeGuard: --front-end-version never fetches a frontend unless opted in."""

from unittest.mock import patch

from app.frontend_management import FrontendManager


def test_frontend_download_refused_by_default(monkeypatch):
    monkeypatch.delenv("ALLOW_FRONTEND_DOWNLOAD", raising=False)
    with (
        patch("app.frontend_management.requests.get") as get,
        patch("app.frontend_management.download_release_asset_zip") as download,
    ):
        path = FrontendManager.init_frontend_unsafe("test-owner/test-repo@1.0.0")
    assert path == FrontendManager.default_frontend_path()
    get.assert_not_called()
    download.assert_not_called()

"""Suite-wide setup for tests-unit (ForgeGuard fork).

pytest imports every test module in one process, and importing
comfy.model_management selects a torch device at import time. Upstream's
comfy_api_nodes tests ran ``args.cpu = True`` on CPU-only machines before any
other module imported it, which kept CPU-only CI working. The fork removes
those tests with the API nodes, so the same switch lives here; without it,
collection crashes with "Torch not compiled with CUDA enabled".

torch is optional: the ForgeGuard CI job runs its tests without it.
"""

import pytest

try:
    import torch
except ImportError:
    torch = None

if torch is not None and not torch.cuda.is_available():
    from comfy.cli_args import args

    args.cpu = True


@pytest.fixture
def file_db(tmp_path, monkeypatch):
    """The real file database: WAL mode, both engines and their hooks, in ``tmp_path``."""
    from app.database import db as db_module

    db_path = str(tmp_path / "comfyui.db")
    monkeypatch.setattr(db_module.args, "database_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(db_module, "Session", None)
    monkeypatch.setattr(db_module, "WriteSession", None)
    monkeypatch.setattr(db_module, "_db_lock", None)
    db_module._init_file_db(db_module.args.database_url)
    yield db_path
    db_module.Session.kw["bind"].dispose()
    db_module.WriteSession.kw["bind"].dispose()
    db_module._db_lock.release(force=True)

"""Suite-wide setup for tests-unit (ForgeGuard fork).

pytest imports every test module in one process, and importing
comfy.model_management selects a torch device at import time. Upstream's
comfy_api_nodes tests ran ``args.cpu = True`` on CPU-only machines before any
other module imported it, which kept CPU-only CI working. The fork removes
those tests with the API nodes, so the same switch lives here; without it,
collection crashes with "Torch not compiled with CUDA enabled".

torch is optional: the ForgeGuard CI job runs its tests without it.
"""

try:
    import torch
except ImportError:
    torch = None

if torch is not None and not torch.cuda.is_available():
    from comfy.cli_args import args

    args.cpu = True

"""ForgeGuard compatibility shims between the fork and the bundled frontend."""

from __future__ import annotations

import os

OFFLINE_SIGNAL = "--disable-api-nodes"


def sanitized_argv(argv: list[str]) -> list[str]:
    """Command-line flag names for ``GET /system_stats``, with every value dropped.

    Upstream returns ``sys.argv`` verbatim, which discloses the paths, URLs and
    secrets passed as flag values. The frontend only needs flag names: it lists
    them in the About panel and keys behavior off them (it skips its
    release-notes check when it sees ``--disable-api-nodes``). This fork is
    permanently offline, so that flag is always reported.
    """
    flags: list[str] = []
    for arg in argv[1:]:
        if arg.startswith("--"):
            name = arg.split("=", 1)[0]
            if name not in flags:
                flags.append(name)
    if OFFLINE_SIGNAL not in flags:
        flags.append(OFFLINE_SIGNAL)
    program = os.path.basename(argv[0]) if argv else "main.py"
    return [program] + flags

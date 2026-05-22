#!/usr/bin/env python
"""Django CLI entrypoint for OmniPOS."""

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
_APPS_ROOT = _REPO_ROOT / "apps"
if str(_APPS_ROOT) not in sys.path:
    sys.path.insert(0, str(_APPS_ROOT))


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

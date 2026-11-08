#!/usr/bin/env python
"""Django 管理入口。"""

import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover
        raise ImportError("未找到 Django，请先激活虚拟环境：source backend/.venv/bin/activate") from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

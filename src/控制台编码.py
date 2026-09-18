# -*- coding: utf-8 -*-
"""
夸克自动搜题 - 控制台编码兜底

Windows 命令行默认是 GBK 码页，直接 print 中文或符号可能抛 UnicodeEncodeError。
在入口脚本最开头 import 这个模块，把 stdout/stderr 统一切到 UTF-8，
并且遇到实在编不出来的字符用替代符号顶上，绝不因为打印而崩掉主流程。
"""

from __future__ import annotations

import sys


def _reconfigure(stream) -> None:
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass


_reconfigure(sys.stdout)
_reconfigure(sys.stderr)

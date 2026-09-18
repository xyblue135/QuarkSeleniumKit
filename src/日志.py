# -*- coding: utf-8 -*-
"""
夸克自动搜题 - 极简日志

控制台永远输出，文件日志按天切分，写入 logs/YYYY-MM-DD.log。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from 配置 import CONFIG


class Logger:
    def __init__(self, write_file: bool | None = None) -> None:
        self.write_file = CONFIG.write_log_file if write_file is None else write_file
        self._fp = None
        if self.write_file:
            try:
                CONFIG.log_dir.mkdir(parents=True, exist_ok=True)
                log_path = CONFIG.log_dir / f"{time.strftime('%Y-%m-%d')}.log"
                self._fp = log_path.open("a", encoding="utf-8")
                self._raw(f"\n===== 启动 {time.strftime('%Y-%m-%d %H:%M:%S')} =====")
            except Exception as exc:  # noqa: BLE001
                print(f"[日志] 无法写入日志文件，已改为仅控制台输出：{exc}")
                self.write_file = False
                self._fp = None

    # ------------------------------------------------------------ 内部

    def _raw(self, line: str) -> None:
        if self._fp:
            try:
                self._fp.write(line + "\n")
                self._fp.flush()
            except Exception:  # noqa: BLE001
                pass

    def _emit(self, level: str, message: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        line = f"[{stamp}] {level} {message}"
        print(line)
        sys.stdout.flush()
        self._raw(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {level} {message}")

    # ------------------------------------------------------------ 对外

    def info(self, message: str) -> None:
        self._emit("[-]", message)

    def ok(self, message: str) -> None:
        self._emit("[+]", message)

    def warn(self, message: str) -> None:
        self._emit("[!]", message)

    def error(self, message: str) -> None:
        self._emit("[x]", message)

    def plain(self, message: str = "") -> None:
        print(message)
        sys.stdout.flush()
        if message:
            self._raw(message)

    def close(self) -> None:
        if self._fp:
            try:
                self._fp.close()
            except Exception:  # noqa: BLE001
                pass
            self._fp = None

# -*- coding: utf-8 -*-
"""
夸克自动搜题 - 截图来源管理

负责：
  1. 在截图目录里找出最新的一张图
  2. 等待文件写完再交给上传（截图程序可能正在写盘）
  3. 判断这张图和上次是不是同一张，避免重复上传浪费额度
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from 配置 import CONFIG


@dataclass(frozen=True)
class ImageFingerprint:
    """用来判断两次拿到的是不是同一张图。"""

    path: str
    mtime: float
    size: int

    @classmethod
    def of(cls, path: Path) -> "ImageFingerprint":
        stat = path.stat()
        return cls(path=str(path), mtime=stat.st_mtime, size=stat.st_size)


class ImageNotReady(RuntimeError):
    """图片还没写完，或者是个空文件。"""


def get_latest_image_path() -> Path:
    """返回匹配前缀的、最后修改时间最新的一张 png。"""
    image_dir = CONFIG.image_dir
    if not image_dir.exists():
        raise FileNotFoundError(f"截图目录不存在：{image_dir}")

    candidates: set[Path] = set()

    exact = image_dir / f"{CONFIG.image_basename}.png"
    if exact.exists():
        candidates.add(exact)

    for path in image_dir.glob(CONFIG.image_pattern):
        if path.is_file():
            candidates.add(path)

    if not candidates:
        raise FileNotFoundError(
            f"没有找到截图：{image_dir}\\{CONFIG.image_pattern}\n"
            "请确认截图程序在运行，或修改 配置.py 里的 image_dir / image_basename。"
        )

    return max(candidates, key=lambda p: p.stat().st_mtime)


def wait_until_file_stable(
    image_path: Path,
    max_wait_seconds: float = 5.0,
    poll_interval: float = 0.25,
    required_stable_polls: int = 2,
) -> None:
    """
    等到文件大小连续多次不变，才认为写盘完成。
    截图程序正在写文件时上传，夸克会收到一张残缺的图。
    """
    last_size = -1
    stable = 0
    deadline = time.monotonic() + max_wait_seconds

    while time.monotonic() < deadline:
        try:
            size = image_path.stat().st_size
        except FileNotFoundError as exc:
            raise ImageNotReady(f"图片刚刚消失了：{image_path}") from exc

        if size > 0 and size == last_size:
            stable += 1
            if stable >= required_stable_polls:
                return
        else:
            stable = 0
            last_size = size

        time.sleep(poll_interval)

    raise ImageNotReady(f"图片仍在写入或为空：{image_path}")


class ImagePicker:
    """带去重记忆的取图器。"""

    def __init__(self) -> None:
        self._last: ImageFingerprint | None = None

    def reset(self) -> None:
        """清空记忆，下一次取图一定会返回图片。"""
        self._last = None

    def pick(self, force: bool = False) -> tuple[Path, bool]:
        """
        返回 (图片路径, 是否为新图)。
        force=True 时即使图片没变化也照常返回，用于手动触发上传。
        """
        path = get_latest_image_path()
        wait_until_file_stable(path)

        fingerprint = ImageFingerprint.of(path)
        is_new = self._last is None or fingerprint != self._last
        self._last = fingerprint

        if not is_new and not force and CONFIG.skip_unchanged_image:
            return path, False
        return path, True

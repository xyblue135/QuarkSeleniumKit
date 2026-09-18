# -*- coding: utf-8 -*-
"""
夸克自动搜题 - 主程序

行为：
  启动后先上传一次最新截图
  之后每隔一段随机时间自动上传一次
  命令行窗口获得焦点时，可用快捷键手动干预

快捷键（必须让命令行窗口处于前台）：
  F8   立即上传一次（忽略去重）
  P    暂停 / 继续自动上传
  R    重新加载夸克页面
  +/-  调大 / 调小上传间隔
  Q    退出

用法：
  python 自动搜题.py
  python 自动搜题.py --interval 15 30
  python 自动搜题.py --once
"""

from __future__ import annotations

import 控制台编码  # noqa: F401  统一控制台编码，必须最先导入

import argparse
import msvcrt
import random
import sys
import time

from selenium.common.exceptions import WebDriverException

from 配置 import CONFIG
from 截图来源 import ImageNotReady, ImagePicker
from 日志 import Logger
from 驱动 import build_driver, explain_startup_error
from 页面操作 import (
    UploadControlNotFound,
    grab_result_text,
    is_logged_in,
    open_search_page,
    upload_image,
)

# msvcrt 里功能键会先返回一个前缀字节，再返回实际编码
KEY_PREFIXES = (b"\x00", b"\xe0")
F8_CODE = b"B"


class AutoSearcher:
    def __init__(self, log: Logger) -> None:
        self.log = log
        self.driver = None
        self.picker = ImagePicker()

        self.min_delay = CONFIG.min_delay_seconds
        self.max_delay = CONFIG.max_delay_seconds

        self.paused = False
        self.should_quit = False

        self.uploaded = 0
        self.skipped = 0
        self.failed = 0
        self.consecutive_failures = 0

    # ------------------------------------------------------------ 生命周期

    def start(self) -> bool:
        self.log.info("正在启动 Chrome ...")
        try:
            self.driver = build_driver()
        except WebDriverException as exc:
            self.log.error("Chrome 启动失败")
            self.log.plain(explain_startup_error(exc))
            return False
        except Exception as exc:  # noqa: BLE001
            self.log.error(f"Chrome 启动失败：{exc}")
            return False

        self.log.info("正在打开夸克搜题页面 ...")
        try:
            open_search_page(self.driver)
        except Exception as exc:  # noqa: BLE001
            self.log.error(f"页面打开失败：{exc}")
            return False

        self.log.ok(f"页面已打开：{self.driver.title or '(无标题)'}")

        if not is_logged_in(self.driver):
            self.log.warn("页面上似乎还有登录入口，如果上传失败请先运行 登录.py 完成登录。")

        return True

    def stop(self) -> None:
        # 故意不调用 driver.quit()：detach=True，让浏览器窗口留给用户看结果
        self.log.plain("")
        self.log.info(
            f"本次统计 — 成功 {self.uploaded} 次，跳过 {self.skipped} 次，失败 {self.failed} 次"
        )
        self.log.info("浏览器窗口保留未关闭，下次运行前请手动关掉它，避免 profile 被占用。")

    # ------------------------------------------------------------ 上传

    def do_upload(self, force: bool = False, tag: str = "自动") -> None:
        try:
            image_path, is_new = self.picker.pick(force=force)
        except (FileNotFoundError, ImageNotReady) as exc:
            self.failed += 1
            self.consecutive_failures += 1
            self.log.error(f"[{tag}] 取图失败：{exc}")
            return

        if not is_new:
            self.skipped += 1
            self.log.info(f"[{tag}] 截图没有变化，跳过（按 F8 可强制上传）")
            return

        try:
            upload_image(self.driver, image_path)
        except UploadControlNotFound as exc:
            self.failed += 1
            self.consecutive_failures += 1
            self.log.error(f"[{tag}] 上传失败")
            self.log.plain(str(exc))
            return
        except WebDriverException as exc:
            self.failed += 1
            self.consecutive_failures += 1
            self.log.error(f"[{tag}] 浏览器异常：{explain_startup_error(exc)}")
            return
        except Exception as exc:  # noqa: BLE001
            self.failed += 1
            self.consecutive_failures += 1
            self.log.error(f"[{tag}] 上传失败：{exc}")
            return

        self.uploaded += 1
        self.consecutive_failures = 0
        self.log.ok(f"[{tag}] 已上传：{image_path.name}")

        if CONFIG.result_wait_seconds > 0:
            try:
                text = grab_result_text(self.driver, CONFIG.result_wait_seconds)
            except Exception:  # noqa: BLE001
                text = ""
            if text:
                preview = text[:120] + ("..." if len(text) > 120 else "")
                self.log.plain(f"        结果：{preview}")

    # ------------------------------------------------------------ 间隔

    def next_delay(self) -> float:
        delay = random.uniform(self.min_delay, self.max_delay)
        if self.consecutive_failures >= 2 and CONFIG.backoff_factor > 1.0:
            factor = CONFIG.backoff_factor ** (self.consecutive_failures - 1)
            delay = min(delay * factor, CONFIG.max_backoff_seconds)
            self.log.warn(
                f"连续失败 {self.consecutive_failures} 次，本次等待放大到 {delay:.0f} 秒"
            )
        return delay

    def adjust_interval(self, step: float) -> None:
        self.min_delay = max(1.0, self.min_delay + step)
        self.max_delay = max(self.min_delay + 1.0, self.max_delay + step)
        self.log.info(f"上传间隔调整为 {self.min_delay:.0f}-{self.max_delay:.0f} 秒")

    # ------------------------------------------------------------ 按键

    def handle_key(self, key: bytes) -> None:
        # 功能键：读掉第二个字节
        if key in KEY_PREFIXES:
            code = msvcrt.getch()
            if code == F8_CODE:
                self.do_upload(force=True, tag="手动")
            return

        lowered = key.lower()

        if lowered == b"q":
            self.should_quit = True
            self.log.info("收到退出指令")
        elif lowered == b"p":
            self.paused = not self.paused
            self.log.info("已暂停自动上传" if self.paused else "已恢复自动上传")
        elif lowered == b"r":
            self.log.info("正在重新加载页面 ...")
            try:
                open_search_page(self.driver)
                self.picker.reset()
                self.log.ok("页面已重新加载")
            except Exception as exc:  # noqa: BLE001
                self.log.error(f"重新加载失败：{exc}")
        elif key in (b"+", b"="):
            self.adjust_interval(+2.0)
        elif key in (b"-", b"_"):
            self.adjust_interval(-2.0)

    def drain_keys(self) -> None:
        while msvcrt.kbhit() and not self.should_quit:
            self.handle_key(msvcrt.getch())

    # ------------------------------------------------------------ 主循环

    def print_help(self) -> None:
        self.log.plain("")
        self.log.plain("-" * 58)
        self.log.plain("  快捷键（需让本命令行窗口处于前台）")
        self.log.plain("    F8    立即上传一次（忽略去重）")
        self.log.plain("    P     暂停 / 继续")
        self.log.plain("    R     重新加载夸克页面")
        self.log.plain("    + -   调大 / 调小上传间隔")
        self.log.plain("    Q     退出")
        self.log.plain("-" * 58)
        self.log.plain("")

    def run_loop(self) -> None:
        self.print_help()
        self.do_upload(force=True, tag="首次")

        while not self.should_quit:
            delay = self.next_delay()
            deadline = time.monotonic() + delay

            while time.monotonic() < deadline:
                if self.should_quit:
                    return
                self.drain_keys()
                if self.paused:
                    # 暂停时不让计时继续推进
                    deadline = time.monotonic() + delay
                time.sleep(0.05)

            if self.should_quit:
                return
            if not self.paused:
                self.do_upload(force=False, tag="自动")
            self.drain_keys()


# ---------------------------------------------------------------- 入口

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="夸克自动搜题：自动上传最新截图并抓取识别结果"
    )
    parser.add_argument(
        "--interval",
        nargs=2,
        type=float,
        metavar=("MIN", "MAX"),
        help="上传间隔秒数范围，例如 --interval 15 30",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="只上传一次就退出，用于快速验证",
    )
    parser.add_argument(
        "--no-log-file",
        action="store_true",
        help="不写日志文件，仅控制台输出",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    log = Logger(write_file=not args.no_log_file)

    log.plain("=" * 58)
    log.plain("  夸克自动搜题")
    log.plain("=" * 58)
    log.plain(CONFIG.describe())
    log.plain("=" * 58)

    searcher = AutoSearcher(log)
    if args.interval:
        searcher.min_delay, searcher.max_delay = sorted(args.interval)

    if not searcher.start():
        log.close()
        return 1

    try:
        if args.once:
            searcher.do_upload(force=True, tag="单次")
        else:
            searcher.run_loop()
    except KeyboardInterrupt:
        log.plain("")
        log.info("已被 Ctrl+C 中断")
    finally:
        searcher.stop()
        log.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())

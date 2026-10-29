# -*- coding: utf-8 -*-
"""
夸克手动搜题 - 纯命令行、双击即用

默认行为（交互模式）：
  启动 Chrome → 进入交互循环，等待你在命令行里按键：
    · 直接按回车（或输入任意内容后回车） → 搜「当前最新的一张截图」这一题
    · 输入 q / quit / exit → 退出（浏览器默认保留，方便看结果）
  不弹 GUI 窗口、不监听麦克风，纯粹“按键才搜一题”。

单次模式（--once）：
  启动 Chrome → 搜一题 → 退出。

前置：
  需先用 1-登录夸克.bat 完成一次登录（登录态会保存在 Chrome 档案里）。

用法：
  python 手动搜题.py               进入交互模式（回车搜下一题，q 退出）
  python 手动搜题.py --once       只搜一题就退出
  python 手动搜题.py --close      退出时直接关闭浏览器窗口（默认保留）
  python 手动搜题.py --no-log-file 不写日志文件，仅控制台输出
  python 手动搜题.py --force      忽略 8 秒最小间隔（不推荐，容易触发风控）
"""

from __future__ import annotations

import 控制台编码  # noqa: F401  统一控制台编码，必须最先导入

import argparse
import sys
import time

from 配置 import CONFIG
from 日志 import Logger
from 自动搜题 import AutoSearcher

# 防封：两次手动搜题之间的最小间隔（秒）。
# 手动模式每次回车都是 force=True，连按回车会连续上传同一题，最容易触发风控，
# 所以这里硬性拦一道。真需要连搜，加 --force 参数自行承担风险。
MIN_GAP_SECONDS = 8.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="夸克手动搜题：交互式 CLI（回车搜下一题）")
    parser.add_argument(
        "--once",
        action="store_true",
        help="只搜一题就退出（不进入交互循环）",
    )
    parser.add_argument(
        "--close",
        action="store_true",
        help="退出时直接关闭浏览器窗口（默认保留窗口，方便看识别结果）",
    )
    parser.add_argument(
        "--no-log-file",
        action="store_true",
        help="不写日志文件，仅控制台输出",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=f"忽略两次搜题之间的 {MIN_GAP_SECONDS:.0f} 秒最小间隔（不推荐，容易触发风控）",
    )
    return parser.parse_args()


def interactive_loop(searcher: AutoSearcher, log: Logger, ignore_gap: bool = False) -> None:
    """交互循环：回车搜下一题，q 退出。浏览器在循环期间保持打开。"""
    log.plain("")
    log.plain("已进入手动模式（CLI）：")
    log.plain("  · 按回车              → 搜索当前这一题")
    log.plain("  · 输入任意文字+回车   → 同样触发搜索下一题")
    log.plain("  · 输入 q / quit / exit → 退出（浏览器默认保留）")
    log.plain("（浏览器窗口会一直开着，方便你逐题查看识别结果；换题前请先让截屏程序截下新画面）")
    if not ignore_gap:
        log.plain(f"（防风控：两题之间至少间隔 {MIN_GAP_SECONDS:.0f} 秒，连按回车会被拦下）")
    log.plain("-" * 58)
    count = 0
    last_upload_at = 0.0
    while True:
        try:
            cmd = input(">>> 回车搜题 / q 退出: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            log.plain("")
            log.info("已退出（EOF/Ctrl+C）")
            break
        if cmd in ("q", "quit", "exit"):
            log.info("已退出手动模式")
            break
        # 频率闸门：手动模式下每按一次回车都是一次真实上传，必须限速
        if not ignore_gap:
            elapsed = time.monotonic() - last_upload_at
            if last_upload_at and elapsed < MIN_GAP_SECONDS:
                log.warn(
                    f"太快了：距上次搜题才 {elapsed:.0f} 秒，"
                    f"请再等 {MIN_GAP_SECONDS - elapsed:.0f} 秒（连点容易被风控）"
                )
                continue
        # 空回车或任意其它输入都视为“搜下一题”
        try:
            searcher.do_upload(force=True, tag="手动")
            last_upload_at = time.monotonic()
            count += 1
        except KeyboardInterrupt:
            log.plain("")
            log.info("本题被 Ctrl+C 中断，继续等待指令")
            continue
        except Exception as exc:  # noqa: BLE001
            log.error(f"搜题出错：{exc}")
            last_upload_at = time.monotonic()
    log.plain(f"本次手动共搜 {count} 题")


def main() -> int:
    args = parse_args()
    log = Logger(write_file=not args.no_log_file)

    log.plain("=" * 58)
    log.plain("  夸克手动搜题（CLI 交互）" if not args.once else "  夸克手动搜题（单次）")
    log.plain("=" * 58)
    log.plain(CONFIG.describe())
    log.plain("=" * 58)
    log.plain("提示：需先用 1-登录夸克.bat 完成登录；若提示 profile 被占用，")
    log.plain("      请先关掉上一个还开着的 Chrome 窗口再运行本脚本。")
    log.plain("-" * 58)

    searcher = AutoSearcher(log)
    if not searcher.start():
        log.error("Chrome 启动失败，无法搜题。请先确认已登录、且没有其他 Chrome 占用档案。")
        log.close()
        return 1

    try:
        if args.once:
            searcher.do_upload(force=True, tag="手动")
        else:
            interactive_loop(searcher, log, ignore_gap=args.force)
    except KeyboardInterrupt:
        log.plain("")
        log.info("已被 Ctrl+C 中断")
    finally:
        # 退出时浏览器处理：--close 关闭，否则保留（detach）方便看结果
        if args.close:
            try:
                if searcher.driver is not None:
                    searcher.driver.quit()
            except Exception:  # noqa: BLE001
                pass
            log.info("已关闭浏览器窗口")
        else:
            searcher.stop()
        log.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())

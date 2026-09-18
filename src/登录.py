# -*- coding: utf-8 -*-
"""
夸克自动搜题 - 登录并保存登录态

为什么用独立 Chrome profile 而不是只导 Cookie：
夸克的登录态不一定只放在 Cookie 里，还可能分布在
localStorage / sessionStorage / IndexedDB / Service Worker 缓存。
整个 profile 目录一起复用最稳。

用法：
  python 登录.py
  1. 脚本会打开一个专用 Chrome 窗口
  2. 在里面扫码或输入账号完成夸克登录
  3. 登录成功后直接关闭该窗口
  4. 登录态会留在 profile 目录里，之后 自动搜题.py 会自动复用
"""

from __future__ import annotations

import 控制台编码  # noqa: F401  统一控制台编码，必须最先导入

import sys

from selenium.common.exceptions import WebDriverException

from 配置 import CONFIG
from 驱动 import build_driver, explain_startup_error
from 页面操作 import is_logged_in, open_search_page


def main() -> int:
    print("=" * 58)
    print("  夸克登录态保存")
    print("=" * 58)
    print(f"  Chrome 档案目录：{CONFIG.profile_dir}")
    print("=" * 58)
    print()

    try:
        driver = build_driver()
    except WebDriverException as exc:
        print("Chrome 启动失败：")
        print(explain_startup_error(exc))
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Chrome 启动失败：{exc}")
        return 1

    try:
        open_search_page(driver)
    except Exception as exc:  # noqa: BLE001
        print(f"页面打开失败：{exc}")
        return 1

    print(f"已打开：{driver.current_url}")
    print(f"标题　：{driver.title or '(无标题)'}")
    print()

    if is_logged_in(driver):
        print("看起来这个档案已经是登录状态了。")
        print("如果实际未登录（或想换账号），在窗口里重新登录即可。")
    else:
        print("当前未登录。")

    print()
    print("请在弹出的 Chrome 窗口里完成夸克登录。")
    print("登录完成后，直接关闭那个窗口，登录态会自动保存。")
    print()
    print("重要：运行 自动搜题.py 之前，务必先关掉这个登录窗口，")
    print("      否则会提示 user data directory is already in use。")

    return 0


if __name__ == "__main__":
    sys.exit(main())

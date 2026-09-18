# -*- coding: utf-8 -*-
"""
夸克自动搜题 - 环境自检

出问题时先跑这个，它会逐项检查并给出修复建议：
  Python 版本 / selenium 包 / Chrome / ChromeDriver 匹配 /
  profile 目录 / 截图目录 / 实际启动一次浏览器

用法：
  python 环境检查.py            # 完整检查（含启动浏览器）
  python 环境检查.py --no-browser   # 跳过启动浏览器
"""

from __future__ import annotations

import 控制台编码  # noqa: F401  统一控制台编码，必须最先导入

import argparse
import sys
from pathlib import Path

OK = "[ OK ]"
WARN = "[WARN]"
FAIL = "[FAIL]"

results: list[tuple[str, str]] = []


def record(status: str, message: str) -> None:
    results.append((status, message))
    print(f"{status} {message}")


def check_python() -> None:
    version = sys.version.split()[0]
    if sys.version_info >= (3, 9):
        record(OK, f"Python {version}")
    else:
        record(FAIL, f"Python {version} 版本过低，需要 3.9 以上")
    record(OK, f"解释器路径 {sys.executable}")


def check_selenium() -> bool:
    try:
        import selenium

        record(OK, f"selenium {selenium.__version__}")
        major = int(selenium.__version__.split(".")[0])
        minor = int(selenium.__version__.split(".")[1])
        if (major, minor) < (4, 6):
            record(
                WARN,
                "selenium 低于 4.6，没有 Selenium Manager，需要手动指定 chromedriver",
            )
        return True
    except ImportError:
        record(FAIL, "没有安装 selenium，请执行：python -m pip install selenium")
        return False


def check_chrome() -> str | None:
    from 驱动 import detect_chrome_version

    version = detect_chrome_version()
    if version:
        record(OK, f"Chrome {version}")
    else:
        record(FAIL, "没有检测到 Chrome，请确认已安装 Google Chrome")
    return version


def check_driver(chrome_version: str | None) -> None:
    from 驱动 import detect_driver_version, major_of, resolve_chromedriver

    path, note = resolve_chromedriver(verbose=False)
    if path is None:
        record(FAIL, f"ChromeDriver 未解析成功：{note}")
        record(
            WARN,
            "如果本机不能联网，请手动下载对应版本驱动并填到 配置.py 的 chromedriver_path",
        )
        return

    driver_version = detect_driver_version(path)
    if chrome_version and major_of(driver_version) != major_of(chrome_version):
        record(
            FAIL,
            f"ChromeDriver {driver_version} 与 Chrome {chrome_version} 主版本不一致",
        )
    else:
        record(OK, f"ChromeDriver {driver_version}")
    record(OK, f"驱动来源 {note}")


def check_paths() -> None:
    from 配置 import CONFIG

    if CONFIG.profile_dir.exists():
        record(OK, f"Chrome 档案目录存在 {CONFIG.profile_dir}")
        default_dir = CONFIG.profile_dir / "Default"
        if default_dir.exists():
            record(OK, "档案里有 Default 子目录，说明之前登录过")
        else:
            record(WARN, "档案里没有 Default 子目录，可能还没登录过，请先运行 登录.py")
    else:
        record(WARN, f"Chrome 档案目录不存在，首次运行会自动创建 {CONFIG.profile_dir}")

    if not CONFIG.image_dir.exists():
        record(FAIL, f"截图目录不存在 {CONFIG.image_dir}")
        record(WARN, "请修改 配置.py 的 image_dir，或先启动截图程序")
        return

    record(OK, f"截图目录存在 {CONFIG.image_dir}")

    images = sorted(
        (p for p in CONFIG.image_dir.glob(CONFIG.image_pattern) if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if images:
        latest = images[0]
        size_kb = latest.stat().st_size / 1024
        record(OK, f"匹配到 {len(images)} 张截图，最新：{latest.name}（{size_kb:.0f} KB）")
    else:
        record(FAIL, f"没有匹配到截图 {CONFIG.image_pattern}")
        record(WARN, "请确认截图程序已运行，或修改 配置.py 的 image_basename")


def check_browser_launch() -> None:
    from selenium.common.exceptions import WebDriverException

    from 驱动 import build_driver, explain_startup_error

    print()
    print("正在尝试启动浏览器（这一步会打开一个 Chrome 窗口）...")
    driver = None
    try:
        driver = build_driver(verbose=False)
        driver.get("data:text/html,<title>Selenium OK</title><h1>Selenium OK</h1>")
        record(OK, f"浏览器可控，页面标题：{driver.title}")
    except WebDriverException as exc:
        record(FAIL, "浏览器启动失败")
        print()
        print(explain_startup_error(exc))
    except Exception as exc:  # noqa: BLE001
        record(FAIL, f"浏览器启动失败：{exc}")
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:  # noqa: BLE001
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description="夸克自动搜题环境自检")
    parser.add_argument(
        "--no-browser", action="store_true", help="跳过实际启动浏览器的检查"
    )
    args = parser.parse_args()

    # 保证能 import 到同目录模块
    sys.path.insert(0, str(Path(__file__).resolve().parent))

    print("=" * 58)
    print("  夸克自动搜题 - 环境自检")
    print("=" * 58)
    print()

    check_python()
    print()

    if not check_selenium():
        return 1
    print()

    chrome_version = check_chrome()
    check_driver(chrome_version)
    print()

    check_paths()

    if not args.no_browser:
        check_browser_launch()

    print()
    print("=" * 58)
    fails = sum(1 for status, _ in results if status == FAIL)
    warns = sum(1 for status, _ in results if status == WARN)
    if fails:
        print(f"  检查结束：{fails} 项失败，{warns} 项提醒。请先解决失败项。")
    elif warns:
        print(f"  检查结束：全部通过，有 {warns} 项提醒。")
    else:
        print("  检查结束：全部通过，可以运行 自动搜题.py")
    print("=" * 58)

    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

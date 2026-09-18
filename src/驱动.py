# -*- coding: utf-8 -*-
"""
夸克自动搜题 - Chrome 驱动管理

解决教程里遗留的一个坑：
教程写死了 chromedriver 149，而本机 Chrome 已经升级到 151，
主版本不匹配会直接启动失败。

这里改成三级策略：
  1. config 里显式指定的 chromedriver 路径
  2. 本地扫描主版本号匹配的驱动（离线优先，避免 Selenium Manager 联网卡死）
  3. Selenium Manager 自动匹配/下载驱动（兜底，需要联网）

只要 Chrome 自动升级，第 2 条会优先用本机已缓存的匹配驱动；
只有本地找不到同主版本驱动时，才回退到第 3 条联网下载。
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from 配置 import CONFIG

# 离线兜底时可能存放 chromedriver 的位置
FALLBACK_DRIVER_DIRS = [
    # 项目根目录下的 drivers：可手动放入与 Chrome 主版本一致的 chromedriver.exe
    Path(__file__).resolve().parent.parent / "drivers",
    # Selenium Manager 自动下载后的默认缓存目录
    Path.home() / ".cache" / "selenium" / "chromedriver",
]

CHROME_EXE_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe",
]


# ---------------------------------------------------------------- 版本探测

def detect_chrome_version() -> str | None:
    """读取本机 Chrome 版本号，例如 151.0.7922.76。"""
    for exe in CHROME_EXE_CANDIDATES:
        if not exe.exists():
            continue
        # chrome.exe --version 在 Windows 上不输出，改读文件版本信息
        try:
            cmd = [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-Item '{exe}').VersionInfo.ProductVersion",
            ]
            out = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15
            ).stdout.strip()
            if re.match(r"^\d+\.", out):
                return out
        except Exception:  # noqa: BLE001
            pass
    return None


def detect_driver_version(driver_path: Path) -> str | None:
    """读取某个 chromedriver.exe 的版本号。"""
    try:
        out = subprocess.run(
            [str(driver_path), "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout.strip()
        match = re.search(r"ChromeDriver\s+(\d+\.\d+\.\d+\.\d+)", out)
        if match:
            return match.group(1)
    except Exception:  # noqa: BLE001
        pass
    return None


def major_of(version: str | None) -> str | None:
    if not version:
        return None
    return version.split(".", 1)[0]


# ---------------------------------------------------------------- 驱动解析

def resolve_via_selenium_manager() -> Path | None:
    """让 Selenium Manager 找/下载与当前 Chrome 匹配的驱动。"""
    try:
        from selenium.webdriver.common.selenium_manager import SeleniumManager

        result = SeleniumManager().binary_paths(["--browser", "chrome"])
        driver_path = result.get("driver_path")
        if driver_path and Path(driver_path).exists():
            return Path(driver_path)
    except Exception as exc:  # noqa: BLE001
        print(f"[驱动] Selenium Manager 不可用：{exc}")
    return None


def scan_local_drivers(want_major: str | None) -> Path | None:
    """在本地常见目录里找主版本匹配的 chromedriver。"""
    if not want_major:
        return None

    seen: list[Path] = []
    for root in FALLBACK_DRIVER_DIRS:
        if not root.exists():
            continue
        try:
            seen.extend(root.glob("**/chromedriver.exe"))
        except Exception:  # noqa: BLE001
            continue

    for candidate in seen:
        if major_of(detect_driver_version(candidate)) == want_major:
            return candidate
    return None


def resolve_chromedriver(verbose: bool = True) -> tuple[Path | None, str]:
    """
    返回 (驱动路径, 说明文字)。
    驱动路径为 None 表示交给 Selenium 内部自行处理。
    """
    chrome_version = detect_chrome_version()
    want_major = major_of(chrome_version)
    if verbose and chrome_version:
        print(f"[驱动] 检测到 Chrome 版本：{chrome_version}")

    # 1) 用户显式指定
    if CONFIG.chromedriver_path:
        path = CONFIG.chromedriver_path
        if path.exists():
            ver = detect_driver_version(path)
            if want_major and major_of(ver) != want_major:
                print(
                    f"[驱动] 警告：指定的驱动是 {ver}，与 Chrome {chrome_version} 主版本不一致，"
                    "可能启动失败。"
                )
            return path, f"配置指定：{path}"
        print(f"[驱动] 配置里指定的驱动不存在：{path}，改用自动匹配。")

    # 2) 本地扫描（离线优先，避免 Selenium Manager 联网卡死）
    local = scan_local_drivers(want_major)
    if local:
        ver = detect_driver_version(local)
        return local, f"本地匹配 {ver or '未知版本'}：{local}"

    # 3) Selenium Manager 兜底（联网下载/匹配）
    auto = resolve_via_selenium_manager()
    if auto:
        ver = detect_driver_version(auto)
        return auto, f"自动匹配 {ver or '未知版本'}：{auto}"

    return None, "未找到可用驱动，交由 Selenium 内部处理"


# ---------------------------------------------------------------- 启动浏览器

def build_options(headless: bool = False) -> Options:
    options = Options()
    options.add_argument(f"--user-data-dir={CONFIG.profile_dir}")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--start-maximized")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-popup-blocking")
    # 关掉“Chrome 正受到自动测试软件的控制”提示条
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    # 脚本结束后浏览器不自动关闭
    options.add_experimental_option("detach", True)
    if headless:
        options.add_argument("--headless=new")
    return options


def build_driver(headless: bool = False, verbose: bool = True) -> webdriver.Chrome:
    """构建一个复用夸克登录态的 Chrome 实例。"""
    CONFIG.profile_dir.mkdir(parents=True, exist_ok=True)

    driver_path, note = resolve_chromedriver(verbose=verbose)
    if verbose:
        print(f"[驱动] {note}")

    options = build_options(headless=headless)
    service = Service(str(driver_path)) if driver_path else Service()

    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(CONFIG.page_load_timeout)
    return driver


def explain_startup_error(exc: Exception) -> str:
    """把常见的 WebDriver 启动错误翻译成人话。"""
    text = str(exc)
    if "user data directory is already in use" in text:
        return (
            "Chrome 用户目录被占用。\n"
            "原因：之前用同一个 profile 打开的 Chrome 还没关闭。\n"
            "处理：关掉之前那个夸克 Chrome 窗口后重新运行。\n"
            "注意：不要去强杀不确定的 Chrome 进程，可能影响你正在用的浏览器。"
        )
    if "This version of ChromeDriver only supports" in text or "session not created" in text:
        return (
            "ChromeDriver 与 Chrome 版本不匹配。\n"
            "处理：把 配置.py 里的 chromedriver_path 留空，让程序自动匹配；\n"
            "      如果本机不能联网，请手动下载与 Chrome 主版本一致的驱动后填入该字段。"
        )
    if "cannot find Chrome binary" in text:
        return "找不到 Chrome 可执行文件，请确认已安装 Google Chrome。"
    return text

# -*- coding: utf-8 -*-
"""
夸克自动搜题 - Chrome 驱动管理

解决教程里遗留的一个坑：
教程写死了 chromedriver 149，而本机 Chrome 已经升级到 151，
主版本不匹配会直接启动失败。

这里改成四级策略：
  1. config 里显式指定的 chromedriver 路径
  2. 本地扫描主版本号匹配的驱动（离线优先，避免 Selenium Manager 联网卡死）
  3. Selenium Manager 自动匹配/下载驱动（官方途径，需要联网）
  4. npmmirror 镜像下载（国内兜底，Selenium Manager 的下载源常连不上）

只要 Chrome 自动升级，第 2 条会优先用本机已缓存的匹配驱动；
本地找不到时走第 3 条；而 Selenium Manager 拿不到匹配驱动时
（典型症状：缓存里只有旧版本、官方下载源 storage.googleapis.com 连不上，
于是它拿旧驱动凑数或直接失败），第 4 条从国内镜像拉匹配版本，
解压到项目 drivers/ 目录，之后第 2 条就能离线命中它。
"""

from __future__ import annotations

import json
import re
import subprocess
import urllib.request
import zipfile
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

# ---------------------------------------------------------------- 镜像兜底

# npmmirror（淘宝）镜像的 chrome-for-testing 二进制仓库，国内可直连。
# 列表接口返回 {"data": [{"name": "156.0.8078.73/", ...}, ...]}
MIRROR_LIST_URL = "https://registry.npmmirror.com/-/binary/chrome-for-testing/"
MIRROR_DOWNLOAD_URL = (
    "https://registry.npmmirror.com/-/binary/chrome-for-testing/"
    "{version}/win64/chromedriver-win64.zip"
)
# 镜像下载的驱动解压到项目 drivers/ 目录（已被 .gitignore 忽略）
MIRROR_INSTALL_DIR = Path(__file__).resolve().parent.parent / "drivers"


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


# ---------------------------------------------------------------- 镜像下载

def _urlopen_maybe_direct(url: str, timeout: float):
    """
    先按系统代理请求，失败后再试直连。
    镜像在国内可直连：代理软件没开/半死不活时不应该挡住下载。
    """
    try:
        return urllib.request.urlopen(url, timeout=timeout)
    except Exception:  # noqa: BLE001
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        return opener.open(url, timeout=timeout)


def pick_mirror_version(major: str, timeout: float = 20.0) -> str | None:
    """从镜像版本列表里挑出该 Chrome 主版本下最新的一个 CfT 版本号。"""
    try:
        with _urlopen_maybe_direct(MIRROR_LIST_URL, timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"[驱动] 镜像版本列表拉取失败：{exc}")
        return None

    items = data if isinstance(data, list) else data.get("data", [])
    candidates: list[tuple[int, ...]] = []
    for item in items:
        name = str(item.get("name", "")).strip("/")
        if not name.startswith(f"{major}."):
            continue
        try:
            candidates.append(tuple(int(part) for part in name.split(".")))
        except ValueError:
            continue
    if not candidates:
        return None
    return ".".join(str(part) for part in max(candidates))


def download_driver_from_mirror(version: str, timeout: float = 300.0) -> Path | None:
    """从镜像下载 chromedriver-win64 并解压到项目 drivers/ 目录。"""
    url = MIRROR_DOWNLOAD_URL.format(version=version)
    target_dir = MIRROR_INSTALL_DIR / f"chromedriver-{version}"
    target = target_dir / "chromedriver.exe"
    if target.exists():
        return target

    zip_path = MIRROR_INSTALL_DIR / f"chromedriver-{version}-win64.zip"
    MIRROR_INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[驱动] 正在从镜像下载 chromedriver {version} ...")
    try:
        with _urlopen_maybe_direct(url, timeout) as resp:
            with zip_path.open("wb") as fp:
                while True:
                    chunk = resp.read(1 << 16)
                    if not chunk:
                        break
                    fp.write(chunk)
    except Exception as exc:  # noqa: BLE001
        print(f"[驱动] 镜像下载失败：{exc}")
        zip_path.unlink(missing_ok=True)
        return None

    try:
        with zipfile.ZipFile(zip_path) as zf:
            member = next(
                name for name in zf.namelist() if name.endswith("/chromedriver.exe")
            )
            target_dir.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(member))
    except Exception as exc:  # noqa: BLE001
        print(f"[驱动] 解压失败：{exc}")
        zip_path.unlink(missing_ok=True)
        return None
    zip_path.unlink(missing_ok=True)

    if major_of(detect_driver_version(target)) != major_of(version):
        print("[驱动] 下载的驱动版本校验不通过，已丢弃。")
        target.unlink(missing_ok=True)
        return None
    return target


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

    # 3) Selenium Manager 兜底（官方途径，联网下载/匹配）
    auto = resolve_via_selenium_manager()
    if auto:
        ver = detect_driver_version(auto)
        if want_major and major_of(ver) != want_major:
            # 典型场景：官方下载源连不上，SM 拿缓存里的旧驱动凑数，不能直接用
            print(
                f"[驱动] Selenium Manager 给出的 {ver} 与 Chrome {chrome_version} "
                "主版本不符，改走镜像下载。"
            )
        else:
            return auto, f"自动匹配 {ver or '未知版本'}：{auto}"

    # 4) npmmirror 镜像下载（Selenium Manager 的官方下载源在国内常被墙）
    if want_major:
        mirror_version = pick_mirror_version(want_major)
        if mirror_version:
            installed = download_driver_from_mirror(mirror_version)
            if installed:
                return installed, f"镜像下载 {mirror_version}：{installed}"

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

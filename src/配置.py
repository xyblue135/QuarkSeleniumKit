# -*- coding: utf-8 -*-
"""
夸克自动搜题 - 配置中心

所有可调参数集中在这里。
如果不想改代码，可以在同目录放一个 config.json 覆盖同名字段，例如：

{
    "image_dir": "D:\\\\my\\\\screenshots",
    "image_basename": "雷电模拟器",
    "min_delay_seconds": 15,
    "max_delay_seconds": 30
}
"""

from __future__ import annotations

import json
from pathlib import Path

# ---------------------------------------------------------------- 基础路径

# 项目根目录（本文件在 src/ 内，上一级才是项目根）
BASE_DIR = Path(__file__).resolve().parent.parent

# 日志目录
LOG_DIR = BASE_DIR / "logs"

# 用户可选的外部配置文件
USER_CONFIG_FILE = BASE_DIR / "config.json"


# ---------------------------------------------------------------- 默认配置

DEFAULTS: dict = {
    # 夸克搜题页面
    "url": "https://vt.quark.cn/blm/qk-souti-759/qk-index?entry=pc_homecard",

    # 截图来源目录
    "image_dir": str(BASE_DIR / "images"),  # 已并入本项目：截屏脚本把图写到本目录 images/

    # 截图文件名前缀，会匹配 前缀*.png
    "image_basename": "雷电模拟器",

    # 独立 Chrome profile，保存夸克登录态（项目内目录，首次运行自动创建）
    "profile_dir": str(BASE_DIR / "chrome-profile"),

    # 备用 chromedriver（离线时使用）。
    # 正常情况下留空即可，程序会用 Selenium Manager 自动匹配当前 Chrome 版本。
    "chromedriver_path": "",

    # 上传间隔（秒），实际间隔在两者之间随机取值
    "min_delay_seconds": 8.0,
    "max_delay_seconds": 12.0,

    # 连续失败时自动放大间隔的倍数，1.0 表示不放大
    "backoff_factor": 1.6,
    # 间隔放大的上限（秒）
    "max_backoff_seconds": 120.0,

    # 同一张截图（路径 + 修改时间 + 大小都没变）是否跳过重复上传
    "skip_unchanged_image": True,

    # 每次上传后，尝试抓取识别结果的等待秒数，0 表示不抓取
    "result_wait_seconds": 6.0,

    # 是否把运行日志写入 logs 目录
    "write_log_file": True,

    # 页面加载超时（秒）
    "page_load_timeout": 30,
}


# ---------------------------------------------------------------- 加载逻辑

def _load_user_overrides() -> dict:
    """读取 config.json，失败时静默忽略，保证主程序可用。"""
    if not USER_CONFIG_FILE.exists():
        return {}
    try:
        with USER_CONFIG_FILE.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        if isinstance(data, dict):
            return data
        print(f"[配置] {USER_CONFIG_FILE.name} 不是一个 JSON 对象，已忽略。")
    except Exception as exc:  # noqa: BLE001
        print(f"[配置] 读取 {USER_CONFIG_FILE.name} 失败，已忽略：{exc}")
    return {}


class Config:
    """把 dict 配置包装成属性访问，顺便做类型规整。"""

    def __init__(self) -> None:
        merged = dict(DEFAULTS)
        overrides = _load_user_overrides()
        unknown = [k for k in overrides if k not in DEFAULTS]
        if unknown:
            print(f"[配置] config.json 中有未知字段，已忽略：{', '.join(unknown)}")
        merged.update({k: v for k, v in overrides.items() if k in DEFAULTS})

        self.url: str = str(merged["url"])
        self.image_dir: Path = Path(str(merged["image_dir"]))
        self.image_basename: str = str(merged["image_basename"])
        self.profile_dir: Path = Path(str(merged["profile_dir"]))

        driver_path = str(merged["chromedriver_path"]).strip()
        self.chromedriver_path: Path | None = Path(driver_path) if driver_path else None

        self.min_delay_seconds: float = float(merged["min_delay_seconds"])
        self.max_delay_seconds: float = float(merged["max_delay_seconds"])
        if self.min_delay_seconds > self.max_delay_seconds:
            self.min_delay_seconds, self.max_delay_seconds = (
                self.max_delay_seconds,
                self.min_delay_seconds,
            )

        self.backoff_factor: float = max(1.0, float(merged["backoff_factor"]))
        self.max_backoff_seconds: float = float(merged["max_backoff_seconds"])
        self.skip_unchanged_image: bool = bool(merged["skip_unchanged_image"])
        self.result_wait_seconds: float = float(merged["result_wait_seconds"])
        self.write_log_file: bool = bool(merged["write_log_file"])
        self.page_load_timeout: int = int(merged["page_load_timeout"])

        self.log_dir: Path = LOG_DIR

    @property
    def image_pattern(self) -> str:
        return f"{self.image_basename}*.png"

    def describe(self) -> str:
        lines = [
            f"  页面地址   : {self.url}",
            f"  截图目录   : {self.image_dir}",
            f"  截图匹配   : {self.image_pattern}",
            f"  Chrome档案 : {self.profile_dir}",
            f"  驱动方式   : "
            + (str(self.chromedriver_path) if self.chromedriver_path else "自动匹配 (Selenium Manager)"),
            f"  上传间隔   : {self.min_delay_seconds:.0f}-{self.max_delay_seconds:.0f} 秒",
        ]
        return "\n".join(lines)


# 全局单例，直接 from 配置 import CONFIG 使用
CONFIG = Config()

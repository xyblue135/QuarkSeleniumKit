# -*- coding: utf-8 -*-
"""
夸克自动搜题 - 页面操作

封装对夸克搜题页面的操作：
  - 打开页面
  - 找到隐藏的 input[type=file] 并塞图片进去
  - 尽力抓取识别结果文本
"""

from __future__ import annotations

import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from 配置 import CONFIG

# “上传图片”按钮，页面改版时优先改这里
UPLOAD_TEXT_XPATH = (
    "//*[contains(concat(' ', normalize-space(@class), ' '), ' i-text ')"
    " and normalize-space()='上传图片']"
)
UPLOAD_TEXT_FALLBACK_XPATH = (
    "//*[normalize-space()='上传图片' or normalize-space()='拍照搜题'"
    " or contains(normalize-space(), '上传图片')]"
)

# 识别结果区域的候选选择器，按优先级尝试
RESULT_SELECTORS = [
    "div[class*='answer']",
    "div[class*='result']",
    "div[class*='content-wrap']",
]


class UploadControlNotFound(RuntimeError):
    """页面上找不到上传控件。"""


def open_search_page(driver: webdriver.Chrome) -> None:
    """打开夸克搜题页并等待 DOM 就绪。"""
    driver.get(CONFIG.url)
    WebDriverWait(driver, CONFIG.page_load_timeout).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )


def _unhide_file_input(driver: webdriver.Chrome, file_input) -> None:
    """
    夸克把 input[type=file] 藏起来了，Selenium 对不可见元素 send_keys 会失败。
    这里临时把它变成一个 1x1 的可见元素，并清掉上一次的值。
    """
    driver.execute_script(
        """
        const input = arguments[0];
        input.value = '';
        input.removeAttribute('hidden');
        input.style.display = 'block';
        input.style.visibility = 'visible';
        input.style.opacity = 1;
        input.style.width = '1px';
        input.style.height = '1px';
        input.style.position = 'fixed';
        input.style.left = '0';
        input.style.top = '0';
        input.style.zIndex = 2147483647;
        """,
        file_input,
    )


def find_file_input(driver: webdriver.Chrome, timeout: float = 10.0):
    """
    找到文件上传输入框。
    页面首次加载时 input 可能还没渲染，需要先点一下“上传图片”把它逼出来。
    """
    inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
    if inputs:
        return inputs[0]

    clicked = False
    for xpath in (UPLOAD_TEXT_XPATH, UPLOAD_TEXT_FALLBACK_XPATH):
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            element.click()
            clicked = True
            break
        except TimeoutException:
            continue

    if clicked:
        time.sleep(0.5)
        inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
        if inputs:
            return inputs[0]

    raise UploadControlNotFound(
        "没有找到 input[type=file]。可能的原因：\n"
        "  1. 还没登录夸克         -> 先运行 登录.py\n"
        "  2. 页面没加载完         -> 稍等片刻后按 F8 重试\n"
        "  3. 夸克页面改版         -> 修改 页面操作.py 里的 UPLOAD_TEXT_XPATH\n"
        "  4. 上传控件在 iframe 里 -> 需要先 switch_to.frame"
    )


def upload_image(driver: webdriver.Chrome, image_path: Path) -> None:
    """把一张本地图片送进夸克搜题页。"""
    file_input = find_file_input(driver)
    _unhide_file_input(driver, file_input)
    file_input.send_keys(str(image_path))


def grab_result_text(driver: webdriver.Chrome, wait_seconds: float) -> str:
    """
    尽力抓取识别结果。
    夸克页面结构会变，这里抓不到就返回空字符串，不影响主流程。
    """
    if wait_seconds <= 0:
        return ""

    deadline = time.monotonic() + wait_seconds
    best = ""

    while time.monotonic() < deadline:
        for selector in RESULT_SELECTORS:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
            except Exception:  # noqa: BLE001
                continue
            for element in elements:
                try:
                    text = (element.text or "").strip()
                except Exception:  # noqa: BLE001
                    continue
                if len(text) > len(best):
                    best = text
        if len(best) > 20:
            break
        time.sleep(0.5)

    return " ".join(best.split())


def is_logged_in(driver: webdriver.Chrome) -> bool:
    """
    粗略判断登录态：页面上如果出现登录/注册入口，就认为没登录。
    只作提示用，不阻断流程。
    """
    try:
        markers = driver.find_elements(
            By.XPATH,
            "//*[normalize-space()='登录' or normalize-space()='立即登录'"
            " or normalize-space()='登录/注册']",
        )
        return not any(m.is_displayed() for m in markers)
    except Exception:  # noqa: BLE001
        return True

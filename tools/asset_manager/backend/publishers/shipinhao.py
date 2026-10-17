# -*- coding: utf-8 -*-
"""微信视频号发布器：上传视频、填标题与话题，自动点击发表。"""
import time

from selenium.webdriver.common.by import By

from . import selenium_base

UPLOAD_URL = "https://channels.weixin.qq.com/platform/post/create"
TITLE_LIMIT = 20
CONFIRM_XPATHS = [
    '//button[contains(@class,"btn") and contains(., "发表")]',
    '//button[normalize-space(.)="发表"]',
    '//div[contains(@class,"button-wrap")]//button[contains(., "发表")]',
]
DRAFT_XPATHS = [
    '//button[contains(@class,"btn") and (contains(., "存草稿") or contains(., "保存草稿") or contains(., "存为草稿"))]',
    '//button[normalize-space(.)="存草稿" or normalize-space(.)="保存草稿" or normalize-space(.)="存为草稿"]',
    '//div[contains(@class,"button-wrap")]//button[contains(., "草稿")]',
    '//button[contains(., "存草稿")]',
    '//button[contains(., "保存草稿")]',
]


def publish(video_path, title, tags, log, publish_mode="publish", content=""):
    xpaths = DRAFT_XPATHS if publish_mode == "draft" else CONFIRM_XPATHS
    return selenium_base.run_publish_flow(
        "shipinhao", UPLOAD_URL, video_path, title, tags, log,
        lambda d, t, tg, l: _fill_form(d, t, tg, l, content=content),
        confirm_xpaths=xpaths, publish_mode=publish_mode)


def _auto_confirm_cover_if_needed(driver, log):
    try:
        candidates = driver.find_elements(
            By.XPATH, '//div[contains(@class,"cover-item") or contains(@class,"frame-item") or contains(@class,"cover-select")]')
        for c in candidates:
            if c.is_displayed():
                c.click()
                time.sleep(0.5)
                for b in driver.find_elements(By.XPATH, '//button[normalize-space(.)="确定" or normalize-space(.)="保存"]'):
                    if b.is_displayed():
                        b.click()
                        log("已自动确认视频默认封面")
                        break
                break
    except Exception:
        pass


def _fill_form(driver, title, tags, log, content=""):
    title_input = selenium_base.wait_for(
        driver, (By.XPATH, '//input[@placeholder="概括视频主要内容，字数建议6-16个字符"]'), 180, "视频上传（标题输入框出现）")
    if title:
        title_input.send_keys(title[:TITLE_LIMIT])
    editor = driver.find_element(By.XPATH, '//div[@class="input-editor"]')
    editor.click()
    if content:
        editor.send_keys(content[:300])
        editor.send_keys(" ")
    for tag in tags or []:
        selenium_base.type_tag(editor, tag, confirm=False)
    time.sleep(1)
    _auto_confirm_cover_if_needed(driver, log)
    log("已填写标题、简介与话题标签")

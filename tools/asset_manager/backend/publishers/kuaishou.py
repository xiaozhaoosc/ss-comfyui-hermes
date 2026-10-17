# -*- coding: utf-8 -*-
"""快手创作者平台发布器：上传视频、填描述与话题，自动点击发布。"""
import time

from selenium.webdriver.common.by import By

from . import selenium_base

UPLOAD_URL = "https://cp.kuaishou.com/article/publish/video"
TITLE_LIMIT = 450
MAX_TAGS = 3  # 快手只接受三个话题标签
CONFIRM_XPATHS = [
    '//button[contains(@class,"primary") and contains(., "发布")]',
    '//button[normalize-space(.)="发布"]',
]


def publish(video_path, title, tags, log, publish_mode="publish"):
    return selenium_base.run_publish_flow(
        "kuaishou", UPLOAD_URL, video_path, title, tags, log, _fill_form,
        confirm_xpaths=CONFIRM_XPATHS, publish_mode=publish_mode)


def _fill_form(driver, title, tags, log):
    # 描述输入框出现代表视频已注入并处理完成
    content = selenium_base.wait_for(
        driver, (By.XPATH, '//div[contains(@placeholder,"添加合适的话题和描述")]'), 180, "视频上传（描述输入框出现）")
    content.click()
    if title:
        content.send_keys(title[:TITLE_LIMIT])
    for tag in (tags or [])[:MAX_TAGS]:
        selenium_base.type_tag(content, tag)
    time.sleep(1)
    log("已填写描述与话题标签")

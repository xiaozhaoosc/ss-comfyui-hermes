# -*- coding: utf-8 -*-
"""抖音创作者平台发布器：上传视频、填标题与话题，自动点击发布。"""
import time

from selenium.webdriver.common.by import By

from . import selenium_base

UPLOAD_URL = "https://creator.douyin.com/creator-micro/content/upload"
TITLE_LIMIT = 30
CONFIRM_XPATHS = [
    '//button[contains(@class,"primary") and contains(., "发布")]',
    '//button[normalize-space(.)="发布"]',
    '//div[contains(@class,"publish-btn") or contains(@class,"submit")]//button',
]


def publish(video_path, title, tags, log, publish_mode="publish"):
    return selenium_base.run_publish_flow(
        "douyin", UPLOAD_URL, video_path, title, tags, log, _fill_form,
        confirm_xpaths=CONFIRM_XPATHS, publish_mode=publish_mode)


def _fill_form(driver, title, tags, log):
    # 标题输入框在视频上传完成后才出现，以此作为上传完毕信号
    title_input = selenium_base.wait_for(
        driver, (By.XPATH, '//input[contains(@class,"semi-input")]'), 180, "视频上传（标题输入框出现）")
    if title:
        title_input.send_keys(title[:TITLE_LIMIT])
    content = driver.find_element(By.XPATH, '//div[@data-placeholder="添加作品简介"]')
    content.click()
    for tag in tags or []:
        selenium_base.type_tag(content, tag)
    time.sleep(1)
    log("已填写标题与话题标签")

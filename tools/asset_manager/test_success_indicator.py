# -*- coding: utf-8 -*-
"""成功提示探测的回归测试。

对应 2026-10-17 的真实事故：`check_success_indicator` 用超宽 XPath 全文档扫描，
在微信编辑器大 DOM 上极慢，且调用点无异常保护，最后抛 ReadTimeout 把整个发布任务打挂
（日志停在「等待保存确认…」，10 分钟后任务 failed）。

这里锁定两条性质：
  1. 能正确认出成功提示 / 不误判普通页面
  2. **任何内部异常都必须被吞掉并返回 False**——它只是辅助信号，绝不允许打挂主任务

用法：venv/Scripts/python.exe tools/asset_manager/test_success_indicator.py
"""
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
for k in list(os.environ):
    if k.lower().endswith("_proxy"):
        os.environ.pop(k)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from backend.publishers.selenium_base import check_success_indicator

PAGE_WITH_TOAST = """<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
<div class="weui-desktop-toast">草稿已保存</div>
</body></html>"""

PAGE_WITH_TIP = """<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
<div class="edit-actions__status">已保存</div>
</body></html>"""

PAGE_PLAIN = """<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
<div class="title">请在这里输入标题</div><p>正文内容</p>
</body></html>"""


class ExplodingDriver:
    """任何调用都抛异常，模拟 chromedriver 读超时 / 连接断开。"""

    def execute_script(self, *a, **kw):
        raise ConnectionResetError("connection aborted")

    def find_elements(self, *a, **kw):
        raise TimeoutError("read timed out")


def main():
    failures = []

    def check(label, actual, expected):
        good = actual == expected
        print(f"  [{'PASS' if good else 'FAIL'}] {label}: {actual!r}")
        if not good:
            failures.append(f"{label}: 期望 {expected!r}，实际 {actual!r}")

    print("1) 内部异常必须被吞掉（本次事故的直接回归点）")
    check("驱动抛异常时返回 False 而不是抛出", check_success_indicator(ExplodingDriver(), "draft"), False)
    check("草稿模式异常同样安全", check_success_indicator(ExplodingDriver(), "publish"), False)

    profile = tempfile.mkdtemp(prefix="success_indicator_test_")
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--no-proxy-server")
    opts.add_argument(f"--user-data-dir={profile}")
    driver = webdriver.Chrome(options=opts)
    try:
        url_t = "file:///" + os.path.join(profile, "toast.html")
        url_p = "file:///" + os.path.join(profile, "tip.html")
        url_n = "file:///" + os.path.join(profile, "plain.html")
        for path, html in ((url_t, PAGE_WITH_TOAST), (url_p, PAGE_WITH_TIP), (url_n, PAGE_PLAIN)):
            with open(path.replace("file:///", ""), "w", encoding="utf-8") as f:
                f.write(html)

        print("\n2) 正常识别")
        driver.get(url_t)
        check("识别 toast「草稿已保存」", check_success_indicator(driver, "draft"), True)
        driver.get(url_p)
        check("识别状态文案「已保存」", check_success_indicator(driver, "draft"), True)
        driver.get(url_n)
        check("普通页面不误判", check_success_indicator(driver, "draft"), False)
    finally:
        driver.quit()

    if failures:
        print("\n失败项：")
        for f in failures:
            print("  - " + f)
        return 1
    print("\n全部通过：成功提示探测能识别结果，且异常不会打挂主任务。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

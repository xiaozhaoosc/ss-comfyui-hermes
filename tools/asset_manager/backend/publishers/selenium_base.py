# -*- coding: utf-8 -*-
"""国内平台 Selenium 发布共享骨架：有头 Chrome + 每平台独立持久化 profile。"""
import os
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from ..config import ASSET_MANAGER_DIR

PROFILE_ROOT = ASSET_MANAGER_DIR / "browser_profiles"
UPLOAD_INPUT_XPATH = '//input[@type="file"]'
MANUAL_CONFIRM_TIMEOUT = 600
AUTO_CONFIRM_TIMEOUT = 240


def _cleanup_stale_profile_locks(profile_dir):
    """清理因异常退出而残留的 profile 占用与 lockfile。"""
    try:
        import psutil
        prof_str = str(profile_dir.resolve()).lower()
        for p in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmd = p.info.get('cmdline') or []
                if p.info.get('name') == 'chrome.exe' and any(prof_str in str(arg).lower() for arg in cmd):
                    p.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass
    lock = profile_dir / "lockfile"
    if lock.exists():
        try:
            lock.unlink()
        except OSError:
            pass


PLATFORM_DEBUG_PORTS = {
    "wechat_mp": 9527,
    "shipinhao": 9528,
    "douyin": 9529,
    "kuaishou": 9530,
}


def _is_port_listening(port, host="127.0.0.1"):
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.6)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False


def _launch_desktop_chrome(platform, profile_dir, port, initial_url=None):
    """通过 Windows 任务计划机制在用户真实物理桌面（WinSta0\\default）上启动 Chrome 并开启 CDP。"""
    import subprocess
    chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if not Path(chrome_exe).exists():
        chrome_exe = "chrome.exe"

    argv = [
        chrome_exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_dir.resolve()}",
        "--start-maximized",
        "--no-first-run",
    ]
    if initial_url:
        argv.append(initial_url)
    cmd = subprocess.list2cmdline(argv)

    task_name = f"AM_Runner_{platform}"
    launched = False
    try:
        created = subprocess.run(["schtasks", "/create", "/tn", task_name, "/tr", cmd, "/sc", "once", "/st", "23:59", "/it", "/f"], capture_output=True)
        ran = subprocess.run(["schtasks", "/run", "/tn", task_name], capture_output=True)
        launched = created.returncode == 0 and ran.returncode == 0
    except OSError:
        launched = False
    if not launched:
        # schtasks 被安全策略拦截或无权限执行时，直接在当前会话拉起 Chrome；
        # 服务运行在用户交互会话内时窗口同样可见，且 Chrome 不随父进程退出而消亡。
        try:
            subprocess.Popen(argv)
        except OSError:
            return False

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if _is_port_listening(port):
            return True
        time.sleep(0.5)
    return False


# chromedriver 会读取 http_proxy，把连本机调试端口的请求也发往代理，
# 代理处理不了时报 "unhandled request"，建会话前必须临时清空这些变量。
_PROXY_ENV_VARS = ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy")


def _start_chrome(options):
    saved = {k: os.environ.pop(k) for k in _PROXY_ENV_VARS if k in os.environ}
    try:
        return webdriver.Chrome(options=options)
    finally:
        os.environ.update(saved)


def build_driver(platform, initial_url=None):
    """连接到用户物理桌面上常驻或新弹出的真实 Chrome 实例（穿透 Windows 会话沙箱）。"""
    profile_dir = PROFILE_ROOT / platform
    profile_dir.mkdir(parents=True, exist_ok=True)
    port = PLATFORM_DEBUG_PORTS.get(platform, 9527)

    # 1. 尝试复用或在真实桌面启动 Chrome
    if not _is_port_listening(port):
        _cleanup_stale_profile_locks(profile_dir)
        _launch_desktop_chrome(platform, profile_dir, port, initial_url=initial_url)

    options = webdriver.ChromeOptions()
    if _is_port_listening(port):
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
        driver = _start_chrome(options)
    else:
        _cleanup_stale_profile_locks(profile_dir)
        options.add_argument(f"--user-data-dir={profile_dir}")
        options.add_argument("--start-maximized")
        options.add_argument("--no-first-run")
        driver = _start_chrome(options)

    driver.implicitly_wait(3)
    return driver


def wait_for(driver, locator, timeout, what):
    try:
        return WebDriverWait(driver, timeout).until(EC.presence_of_element_located(locator))
    except TimeoutException:
        raise TimeoutException(f"等待{what}超时")


def type_tag(content_el, tag, confirm=True):
    """在简介输入框中追加一个 #话题 标签。"""
    tag = tag if tag.startswith("#") else f"#{tag}"
    content_el.send_keys(" ")
    content_el.send_keys(tag)
    time.sleep(1.5)
    if confirm:
        content_el.send_keys(Keys.ENTER)
    time.sleep(1)


def run_publish_flow(platform, upload_url, video_path, title, tags, log, fill_form,
                     confirm_xpaths=None, publish_mode="publish"):
    """发布骨架：打开上传页 -> 注入视频 -> 填表单 -> 确认发布。

    publish_mode:
      - "publish": 自动点击平台发布按钮（confirm_xpaths 依次尝试），成功即返回
      - "draft":   自动点击存草稿类按钮
      - "manual":  停在确认页等人工点击（旧行为）
    自动确认失败（按钮不可用/超时）时降级为人工确认，窗口保持打开。
    """
    driver = build_driver(platform, initial_url=upload_url)
    result = "failed"
    try:
        driver.get(upload_url)
        time.sleep(3)
        try:
            file_input = WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.XPATH, UPLOAD_INPUT_XPATH)))
        except TimeoutException:
            log(f"未检测到上传入口，可能需要登录。窗口已打开，请在窗口中扫码登录（最长等待 180 秒，登录后自动继续）...")
            logged_in = False
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                time.sleep(2)
                try:
                    _ = driver.current_url
                except WebDriverException:
                    log("浏览器窗口已关闭，未完成登录。")
                    result = "need_login"
                    return result
                inputs = driver.find_elements(By.XPATH, UPLOAD_INPUT_XPATH)
                if inputs and any(inp.is_displayed() for inp in inputs):
                    file_input = inputs[0]
                    logged_in = True
                    log(f"检测到登录成功！继续执行发布流程...")
                    time.sleep(2)
                    break
            if not logged_in:
                log("等待扫码登录超时（180 秒），任务结束。")
                result = "need_login"
                return result
        file_input.send_keys(str(Path(video_path).resolve()))
        log(f"已注入视频文件：{Path(video_path).name}")
        fill_form(driver, title, tags, log)
        time.sleep(2)

        if publish_mode == "manual":
            log("表单已填写完成，请在浏览器窗口中检查并点击发布按钮，最长等待 10 分钟。")
            result = _wait_manual_confirm(driver, upload_url, log)
            return result

        button_label = "存草稿" if publish_mode == "draft" else "发布/发表"
        result = _auto_confirm(driver, upload_url, confirm_xpaths or [], publish_mode, log)
        if result is not None:
            return result

        log(f"自动点击{button_label}未生效（可能仍在转码），请人工在浏览器中确认，最长等待 10 分钟。")
        result = _wait_manual_confirm(driver, upload_url, log)
        return result
    except WebDriverException as e:
        log(f"浏览器自动化异常：{e}")
        result = "failed"
        return result
    finally:
        if result != "need_login":
            try:
                driver.quit()
            except WebDriverException:
                pass


def _find_action_button(driver, xpaths, mode="publish"):
    """按候选 XPath 查找可见且可点击的操作按钮。"""
    for xpath in xpaths:
        for el in driver.find_elements(By.XPATH, xpath):
            if not el.is_displayed():
                continue
            text = (el.text or "").strip()
            if mode == "draft":
                if any(k in text for k in ("发表", "发布", "群发", "定时")):
                    continue
            else:
                if any(k in text for k in ("草稿", "定时")):
                    continue
            if text:
                return el
    return None


def check_success_indicator(driver, publish_mode):
    """检测页面中是否出现保存/发布成功的 Toast 或提示消息。"""
    success_keywords = ("保存成功", "草稿保存成功", "已保存", "保存草稿成功") if publish_mode == "draft" else ("发表成功", "发布成功", "上传成功")
    toast_xpaths = [
        '//*[contains(@class,"toast") or contains(@class,"message") or contains(@class,"tips") or contains(@class,"weui-desktop-toast") or contains(@class,"notification")]',
        '//div[contains(@role,"alert") or contains(@role,"status")]',
    ]
    for xpath in toast_xpaths:
        for el in driver.find_elements(By.XPATH, xpath):
            try:
                if el.is_displayed():
                    text = (el.text or "").strip()
                    if any(k in text for k in success_keywords):
                        return True
            except WebDriverException:
                continue
    return False


def _auto_confirm(driver, upload_url, confirm_xpaths, publish_mode, log):
    """轮询点击发布/草稿按钮直到离开上传页或出现成功提示；成功返回状态，未生效返回 None。"""
    label = "存草稿" if publish_mode == "draft" else "发布"
    deadline = time.monotonic() + AUTO_CONFIRM_TIMEOUT
    last_click = 0.0
    while time.monotonic() < deadline:
        time.sleep(2)
        try:
            current = driver.current_url
        except WebDriverException:
            log("浏览器窗口已关闭，无法确认操作是否完成。")
            return "failed"
        if upload_url not in current:
            log(f"页面已跳转，但未收到成功提示，无法确认{label}结果。")
            return "failed"
        if check_success_indicator(driver, publish_mode):
            log(f"检测到操作成功提示，{label}成功。")
            return "success"
        if time.monotonic() - last_click < 6:
            continue
        try:
            button = _find_action_button(driver, confirm_xpaths, mode=publish_mode)
            if button is None:
                continue
            try:
                button.click()
            except WebDriverException:
                driver.execute_script("arguments[0].click();", button)
            last_click = time.monotonic()
            log(f"已自动点击「{label}」按钮，等待平台响应...")
            time.sleep(3)
            if check_success_indicator(driver, publish_mode):
                log(f"检测到操作成功提示，{label}成功。")
                return "success"
        except WebDriverException:
            continue
    return None


def _wait_manual_confirm(driver, upload_url, log):
    deadline = time.monotonic() + MANUAL_CONFIRM_TIMEOUT
    while time.monotonic() < deadline:
        time.sleep(5)
        try:
            if upload_url not in driver.current_url:
                log("检测到已离开上传页面，但未收到成功提示，无法确认操作结果。")
                return "failed"
        except WebDriverException:
            log("浏览器窗口已关闭，无法确认操作是否完成。")
            return "failed"
    log("等待人工确认超时（10 分钟），未能确认操作结果；请到平台后台核实。")
    return "failed"

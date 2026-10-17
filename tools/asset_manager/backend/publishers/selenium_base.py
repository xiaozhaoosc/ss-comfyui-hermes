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


def _reset_debug_tabs(port):
    """把调试 Chrome 里的重页面关掉，换一个空白页。

    微信后台页面会把渲染进程拖到无响应（CDP Page.navigate 都超时），
    chromedriver 建会话时会因此干等 30s~120s+ 甚至 read timeout。
    这些是发布专用浏览器，标签页可随时重建，登录态在 profile 里不受影响。
    先开空白页再关旧页，避免关掉最后一个标签页把 Chrome 一起带走。
    """
    import json as _json
    import urllib.request

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    base = f"http://127.0.0.1:{port}"
    try:
        opener.open(base + "/json/new?about:blank", timeout=5).read()
    except Exception:
        return
    try:
        pages = [t for t in _json.loads(opener.open(base + "/json/list", timeout=8).read().decode("utf-8"))
                 if t.get("type") == "page"]
    except Exception:
        return
    for t in pages:
        if "about:blank" in (t.get("url") or ""):
            continue
        try:
            opener.open(f"{base}/json/close/{t['id']}", timeout=5).read()
        except Exception:
            pass


def build_driver(platform, initial_url=None):
    """连接到用户物理桌面上常驻或新弹出的真实 Chrome 实例（穿透 Windows 会话沙箱）。"""
    profile_dir = PROFILE_ROOT / platform
    profile_dir.mkdir(parents=True, exist_ok=True)
    port = PLATFORM_DEBUG_PORTS.get(platform, 9527)

    # 1. 尝试复用或在真实桌面启动 Chrome
    if not _is_port_listening(port):
        _cleanup_stale_profile_locks(profile_dir)
        _launch_desktop_chrome(platform, profile_dir, port, initial_url=initial_url)
    else:
        _reset_debug_tabs(port)

    options = webdriver.ChromeOptions()
    # 微信编辑器是重页面，normal 策略会等所有子资源加载完（实测 >60s）；
    # eager 在 DOMContentLoaded 即返回，后续流程本来就有显式等待与 sleep。
    options.page_load_strategy = "eager"
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
    # 不设超时时，僵尸标签页会让 chromedriver 建会话无限挂起（实测 >120s 无任何报错），
    # 加了超时至少能抛出异常让上层走降级逻辑。
    driver.set_page_load_timeout(60)
    driver.set_script_timeout(60)
    # 标记这是"附加到常驻 Chrome"的会话：收尾时只能断会话，不能 quit（见 release_driver）
    driver.keep_alive = True
    return driver


def release_driver(driver, log=None):
    """释放 driver 但保留被附加的 Chrome。

    ★ 关键：用 debuggerAddress 附加到常驻 Chrome 时，`driver.quit()` 会把**整个 Chrome 一起关掉**。
    实测后果是每发布一次、9527/9528 就消失一次；下一单只能重新拉浏览器，
    而 schtasks 被安全策略拦截时只能回退到当前会话启动，之后 chromedriver 附加要 35s~180s+、
    经常 120s 读超时，表现为"环境莫名不稳定"。这里只断会话 + 停 chromedriver，Chrome 与登录态常驻。
    """
    if not getattr(driver, "keep_alive", False):
        try:
            driver.quit()
        except Exception:
            pass
        return
    try:
        driver.command_executor.close()
    except Exception:
        pass
    try:
        service = getattr(driver, "service", None)
        if service is not None:
            service.stop()
    except Exception:
        pass
    if log:
        log("已释放自动化会话（保留常驻 Chrome 与登录态）。")


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
            release_driver(driver, log)


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
    """检测页面中是否出现保存/发布成功的提示。

    注意：这里只是"锦上添花"的信号，不能让它拖垮整个任务——
    原实现用 `//*[contains(@class,"toast") or ...]` 做全文档 XPath 扫描，
    在微信编辑器这种超大 DOM 上单次要几十秒，累积能把任务拖到 chromedriver 读超时；
    而且调用点没有异常保护，超时直接把整个发布打成 failed。
    现在改成原生选择器扫描并整体吞异常。
    """
    keywords = ("保存成功", "草稿保存成功", "已保存", "保存草稿成功") if publish_mode == "draft" else ("发表成功", "发布成功", "上传成功")
    try:
        return bool(driver.execute_script("""
            var kws = arguments[0];
            var sels = ['.weui-desktop-toast', '.weui-desktop-tips', '.weui-desktop-msg',
                        '.weui-desktop-notification', '#js_save_status', '.edit-actions__status',
                        '[class*="save-status"]', '[class*="saved-time"]',
                        '[class*="toast"]', '[class*="notice"]',
                        '[role="alert"]', '[role="status"]'];
            for (var i = 0; i < sels.length; i++) {
                var nodes = document.querySelectorAll(sels[i]);
                for (var j = 0; j < nodes.length; j++) {
                    var t = nodes[j].innerText || '';
                    if (!t) continue;
                    for (var k = 0; k < kws.length; k++) {
                        if (t.indexOf(kws[k]) >= 0) return true;
                    }
                }
            }
            return false;
        """, list(keywords)))
    except Exception:
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

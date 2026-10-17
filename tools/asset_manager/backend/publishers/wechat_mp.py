# -*- coding: utf-8 -*-
"""微信公众号后台发布器（实验性）：视频素材 / 贴图 / 图文文章三种模式。

公众号后台为富 iframe 页面，自动化按步骤尽力执行：每一步失败都会写入日志
并降级为人工模式（保持窗口打开等待用户完成），不中断任务。
"""
import time
from pathlib import Path

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By

from . import selenium_base

MP_URL = "https://mp.weixin.qq.com/"
VIDEO_LIST_URL = "https://mp.weixin.qq.com/cgi-bin/filepage?t=media/file_list&type=4&action=browse"
DRAFT_BOX_URL = "https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_list&action=list_card&type=10&lang=zh_CN"
ARTICLE_EDIT_URL = "https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit_v2&action=edit&type=77&lang=zh_CN"
MANUAL_TIMEOUT = 600


def publish(video_path, title, tags, log, publish_mode="publish", media_type="video", content="", image_paths=None):
    try:
        if media_type == "article":
            return _publish_article(video_path, title, tags, log, publish_mode=publish_mode, content=content, image_paths=image_paths)
        if media_type == "images":
            return _publish_images(video_path, title, tags, log, publish_mode=publish_mode, content=content, image_paths=image_paths)
        return _publish_video(video_path, title, tags, log, publish_mode=publish_mode)
    except WebDriverException as e:
        log(f"公众号自动化异常：{e}")
        return "failed"


# ---------------------------------------------------------------------------
# 公共步骤
# ---------------------------------------------------------------------------

def _is_mp_logged_in(driver):
    """严格判定是否已真实登录进入微信公众号后台（必须包含 cgi-bin 或后台特征元素）。"""
    try:
        curr = driver.current_url.lower()
        if "cgi-bin" in curr and ("token=" in curr or "home" in curr):
            return True
        els = driver.find_elements(
            By.XPATH,
            '//div[contains(@class,"weui-desktop-account__info")] | //div[contains(@class,"mp-header")] | //a[contains(@href,"logout")] | //li[contains(@class,"weui-desktop-menu__item")]'
        )
        if any(el.is_displayed() for el in els):
            return True
    except Exception:
        pass
    return False


def _get_mp_token(driver):
    """从当前已登录后台的 URL 中提取 token 参数。"""
    try:
        import urllib.parse
        parsed = urllib.parse.urlparse(driver.current_url)
        qs = urllib.parse.parse_qs(parsed.query)
        tokens = qs.get("token")
        if tokens:
            return tokens[0]
    except Exception:
        pass
    return ""


def _open_mp_logged_in(driver, log, timeout=180):
    """打开公众号后台并确认登录态；未登录则保持窗口打开等待扫码（最长等待 180 秒）。扫码成功后自动继续。"""
    if _is_mp_logged_in(driver):
        log("检测到公众号已处于登录状态，直接进入发布流程。")
        return True

    _safe_navigate(driver, MP_URL, log)
    time.sleep(3)
    if _is_mp_logged_in(driver):
        log("检测到公众号已处于登录状态，直接进入发布流程。")
        return True

    log("检测到微信公众号需要扫码登录，窗口已在物理桌面打开，请在 Chrome 中扫码（最长等待 180 秒，扫码确认后将自动继续）...")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(2)
        try:
            _ = driver.current_url
        except WebDriverException:
            log("浏览器窗口已关闭，未完成登录。")
            return False
        if _is_mp_logged_in(driver):
            log("检测到公众号已成功登录！正在自动继续发布流程...")
            time.sleep(2)
            return True

    log("等待扫码登录超时（180 秒），任务结束。")
    return False


# 公众号页面里存在多个隐藏的 input[type=file]：下拉菜单模板里的、webuploader 上传器里的。
# 注入到模板控件上界面毫无反应（贴图计数一直是 0/20），必须按所属容器打分挑选真上传器。
_FILE_INPUT_RANK_JS = """return (function(){
  var scored = [];
  Array.from(document.querySelectorAll('input[type=file]')).forEach(function(el){
    var uploader = el.closest('.js_upload_btn_container, .webuploader-container, .weui-desktop-upload, [class*="upload"]');
    var inTemplate = !!el.closest('[class*="tpl_"]');
    var score = 0;
    if (uploader) score += 3;
    if (inTemplate) score -= 10;
    if (el.hasAttribute('multiple')) score += 1;
    if (el.offsetParent !== null) score += 1;
    scored.push([el, score]);
  });
  return scored;
})()"""


def _find_file_input_anywhere(driver):
    """在主文档与所有 iframe 中查找真正的文件上传控件。"""
    best, best_score = None, -999
    for frame in [None] + driver.find_elements(By.TAG_NAME, "iframe"):
        try:
            if frame is not None:
                driver.switch_to.frame(frame)
            for el, score in driver.execute_script(_FILE_INPUT_RANK_JS) or []:
                if score > best_score:
                    best, best_score = el, score
            driver.switch_to.default_content()
        except WebDriverException:
            driver.switch_to.default_content()
    return best


def _click_text_button(driver, texts, log, exclude_texts=None):
    """按可见文字查找并点击按钮/链接（主文档+iframe）。"""
    for text in texts:
        xpath = f'//*[self::a or self::button or self::span or self::div][contains(normalize-space(.), "{text}")]'
        for context in ("main", "iframes"):
            try:
                if context == "iframes":
                    frames = driver.find_elements(By.TAG_NAME, "iframe")
                else:
                    frames = [None]
                for frame in frames:
                    if frame is not None:
                        driver.switch_to.frame(frame)
                    els = [el for el in driver.find_elements(By.XPATH, xpath) if el.is_displayed()]
                    if exclude_texts:
                        els = [el for el in els if not any(ex in (el.text or "") for ex in exclude_texts)]
                    if els:
                        target = els[0]
                        try:
                            target.click()
                        except WebDriverException:
                            driver.execute_script("arguments[0].click();", target)
                        if frame is not None:
                            driver.switch_to.default_content()
                        log(f"已点击「{text}」入口。")
                        return True
                    if frame is not None:
                        driver.switch_to.default_content()
            except WebDriverException:
                driver.switch_to.default_content()
    return False


def _draft_in_list_via_api(driver, title, token=None):
    """用页面内 fetch 调公众号草稿列表接口，确认草稿是否真的落库。

    以服务端数据为准，比在页面上猜 Toast/status 文本可靠得多：
    只要草稿箱列表里出现了这条标题，就是真的保存成功了。
    返回 dict：{ok, hit, count, titles}；调用失败返回 ok=False。
    """
    try:
        token = token or _get_mp_token(driver)
        if not token:
            return {"ok": False, "err": "no token"}
        return driver.execute_async_script("""
            var token = arguments[0], want = arguments[1];
            var done = arguments[arguments.length - 1];
            var url = '/cgi-bin/appmsg?token=' + token + '&lang=zh_CN&f=json&ajax=1&random=' + Math.random()
                    + '&action=list_ex&begin=0&count=20&type=77&sub=all&query=';
            fetch(url, { credentials: 'include' })
              .then(function (r) { return r.json(); })
              .then(function (d) {
                  var list = (d && d.app_msg_info) || [];
                  var titles = list.map(function (it) { return it.title || ''; });
                  done({ ok: true, hit: titles.some(function (t) { return t.indexOf(want) >= 0; }),
                         count: titles.length, titles: titles.slice(0, 5) });
              })
              .catch(function (e) { done({ ok: false, err: String(e) }); });
        """, token, title)
    except Exception as e:
        return {"ok": False, "err": str(e)}


def _wait_draft_save_success(driver, log, timeout=60, title=None):
    """轮询检测草稿是否保存成功。

    判定顺序（先快后准）：
      1. URL 出现 appmsgid 且不再有 isNew（微信保存后会改写地址栏）
      2. 页面上出现「已保存 / 草稿已于 …」等状态文案（可选，纯 JS 扫描，不阻塞）
      3. 每若干轮调一次草稿列表接口，确认标题真的落库（最可靠）
    """
    deadline = time.monotonic() + timeout
    token = _get_mp_token(driver)
    round_no = 0
    while time.monotonic() < deadline:
        round_no += 1
        time.sleep(1.5)
        try:
            curr = driver.current_url
            if "appmsgid=" in curr and "isNew" not in curr:
                return True
        except Exception:
            pass

        if selenium_base.check_success_indicator(driver, "draft"):
            return True

        # 状态文案扫描（纯 JS，原实现里这次执行是最慢的一环）
        try:
            saved = driver.execute_script("""
                var statusEls = document.querySelectorAll('#js_save_status, .edit-actions__status, .weui-desktop-tips, [class*="save-status"], [class*="saved-time"]');
                for (var i = 0; i < statusEls.length; i++) {
                    var t = statusEls[i].innerText || '';
                    if (t.indexOf('已保存') >= 0 || t.indexOf('草稿已于') >= 0 || t.indexOf('保存成功') >= 0) return true;
                }
                return false;
            """)
            if saved:
                return True
        except Exception:
            pass

        # 每 4 轮用接口确认一次（服务端数据为准）
        if title and round_no % 4 == 0:
            res = _draft_in_list_via_api(driver, title, token=token)
            if res.get("hit"):
                if log:
                    log(f"草稿列表接口已确认入库：{res.get('titles', [])[:2]}")
                return True

    return False


def _auto_handle_mp_cover(driver, log):
    """若平台出现封面选择弹窗或候选帧，自动选择并确认。"""
    time.sleep(1)
    for frame in [None] + driver.find_elements(By.TAG_NAME, "iframe"):
        try:
            if frame is not None:
                driver.switch_to.frame(frame)
            candidates = driver.find_elements(
                By.XPATH, '//div[contains(@class,"cover-item") or contains(@class,"frame-item") or contains(@class,"img-crop")]')
            for c in candidates:
                if c.is_displayed():
                    c.click()
                    time.sleep(0.5)
                    break
            confirm_btns = driver.find_elements(
                By.XPATH, '//button[normalize-space(.)="确定" or normalize-space(.)="下一步" or normalize-space(.)="完成"]')
            for b in confirm_btns:
                if b.is_displayed():
                    b.click()
                    log("已自动确认视频默认封面。")
                    break
            if frame is not None:
                driver.switch_to.default_content()
        except WebDriverException:
            if frame is not None:
                driver.switch_to.default_content()


def _wait_manual_finish(driver, log, what):
    """等待人工接管；关闭窗口或超时都不能证明草稿已保存。"""
    log(f"剩余步骤请人工在浏览器窗口中完成：{what}（最长等待 10 分钟）。")
    deadline = time.monotonic() + MANUAL_TIMEOUT
    while time.monotonic() < deadline:
        time.sleep(5)
        try:
            _ = driver.current_url
        except WebDriverException:
            log("浏览器窗口已关闭，无法确认操作是否完成。")
            return "failed"
    log("等待人工操作超时，未能确认草稿已保存；请到公众号草稿箱核实。")
    return "failed"


# ---------------------------------------------------------------------------
# 视频消息（存草稿 / 素材库）
# ---------------------------------------------------------------------------

def _publish_video(video_path, title, tags, log, publish_mode="publish"):
    driver = selenium_base.build_driver("wechat_mp", initial_url=MP_URL)
    result = "failed"
    try:
        if not _open_mp_logged_in(driver, log):
            result = "need_login"
            return result

        token = _get_mp_token(driver)
        draft_box_url = f"https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_list&action=list_card&type=10&lang=zh_CN&token={token}" if token else DRAFT_BOX_URL
        video_list_url = f"https://mp.weixin.qq.com/cgi-bin/filepage?t=media/file_list&type=4&action=browse&token={token}&lang=zh_CN" if token else VIDEO_LIST_URL

        if publish_mode == "draft":
            # 存草稿模式：优先寻找「视频消息」草稿入口
            if not _click_text_button(driver, ["视频消息", "新建视频", "新的视频消息"], log):
                # 尝试进入草稿箱页面再找
                _safe_navigate(driver, draft_box_url, log)
                time.sleep(3)
                _click_text_button(driver, ["新建视频", "视频消息"], log)
        else:
            _safe_navigate(driver, video_list_url, log)
            time.sleep(3)

        time.sleep(3)
        file_input = _find_file_input_anywhere(driver)
        if file_input is None:
            # fallback 到素材库
            log("未直接定位到视频上传入口，尝试打开视频素材库页面...")
            _safe_navigate(driver, video_list_url, log)
            time.sleep(3)
            file_input = _find_file_input_anywhere(driver)

        if file_input is None:
            log("未定位到视频上传入口，请人工在公众号后台完成。")
            result = _wait_manual_finish(driver, log, "上传视频并存草稿")
            return result

        file_input.send_keys(str(Path(video_path).resolve()))
        log(f"已注入视频文件：{Path(video_path).name}")
        time.sleep(3)

        _fill_editor_title(driver, title, log)
        _auto_handle_mp_cover(driver, log)

        if publish_mode == "manual":
            result = _wait_manual_finish(driver, log, "人工确认并保存")
            return result

        if publish_mode == "draft":
            clicked = _click_text_button(
                driver, ["保存为草稿", "存为草稿", "保存到草稿箱", "保存"], log,
                exclude_texts=["群发", "发表", "保存并群发"])
            if clicked:
                log("已自动点击「保存为草稿」，等待转码与保存确认...")
                if _wait_draft_save_success(driver, log, timeout=60, title=title):
                    log("视频已全自动保存到公众号草稿箱！")
                    result = "success"
                    return result
            log("自动存草稿未在预期时间内检测到完成，平滑降级为人工确认。")
            result = _wait_manual_finish(driver, log, "等待视频转码并保存到草稿箱")
            return result
        else:
            _click_text_button(driver, ["保存并群发", "发表", "保存"], log)
            result = _wait_manual_finish(driver, log, "确认发表视频")
            return result
    finally:
        if result != "need_login":
            selenium_base.release_driver(driver, log)


# ---------------------------------------------------------------------------
# 贴图（图片消息）
# ---------------------------------------------------------------------------

def _fill_article_body_content(driver, content, log):
    """将正文描述文字插入到微信文章编辑器的 ueditor 中。"""
    if not content:
        return
    for frame in driver.find_elements(By.TAG_NAME, "iframe"):
        try:
            driver.switch_to.frame(frame)
            body = driver.find_element(By.TAG_NAME, "body")
            if body.is_displayed():
                escaped = content.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "<br>")
                driver.execute_script(f"document.body.innerHTML = '<p>{escaped}</p><br>' + document.body.innerHTML;")
                driver.switch_to.default_content()
                log("已成功填入文章正文描述。")
                return
            driver.switch_to.default_content()
        except WebDriverException:
            driver.switch_to.default_content()


def _safe_navigate(driver, url, log=None, settle=3):
    """微信后台页面极重，driver.get 常等不到 load 事件（chromedriver 120s 读超时）。

    超时不代表页面没进去——多数情况下 DOM 已经可用，后续流程本来就会等元素，
    所以这里吞掉超时继续走，避免整个任务白扔 5 分钟再失败。
    """
    try:
        driver.get(url)
    except Exception as e:
        if log:
            log(f"页面导航超时（{type(e).__name__}），按已进入页面继续。")
        time.sleep(settle)


def _fill_image_post_content(driver, content, log):
    """在贴图/图片消息的描述输入框中填入正文描述。"""
    if not content:
        return
    # 1. 优先使用 JS 定位贴图模式的 ProseMirror 描述区域注入
    js_desc = """
    var val = arguments[0];
    // 排除标题框（它在 #js_title_main 里），避免描述写进标题
    var pms = Array.from(document.querySelectorAll('.ProseMirror'))
                  .filter(p => !p.closest('#js_title_main') && !p.closest('.js_title_main'));
    var descPm = pms.find(p => (p.innerText || '').includes('填写描述信息')) || pms[0] || null;
    if (descPm) {
        // ProseMirror 只认浏览器真实输入管线，直接写 innerText 不会同步内部模型
        descPm.focus();
        document.execCommand('selectAll', false, null);
        document.execCommand('delete', false, null);
        document.execCommand('insertText', false, val);
        descPm.dispatchEvent(new Event('input', { bubbles: true }));
        descPm.blur();
        return true;
    }
    return false;
    """
    for frame in [None] + driver.find_elements(By.TAG_NAME, "iframe"):
        try:
            if frame is not None:
                driver.switch_to.frame(frame)
            if driver.execute_script(js_desc, content[:1000]):
                if frame is not None:
                    driver.switch_to.default_content()
                log("已填写贴图正文描述。")
                return
            if frame is not None:
                driver.switch_to.default_content()
        except Exception:
            if frame is not None:
                driver.switch_to.default_content()

    # 2. 备用常规交互
    xpaths = [
        '//div[contains(@class,"input-editor") or contains(@class,"desc-input") or @contenteditable="true"]',
        '//textarea[contains(@placeholder,"写下") or contains(@placeholder,"描述") or contains(@class,"desc")]',
    ]
    for xpath in xpaths:
        for frame in [None] + driver.find_elements(By.TAG_NAME, "iframe"):
            try:
                if frame is not None:
                    driver.switch_to.frame(frame)
                els = driver.find_elements(By.XPATH, xpath)
                for el in els:
                    if el.is_displayed():
                        el.click()
                        el.send_keys(content[:500])
                        if frame is not None:
                            driver.switch_to.default_content()
                        log("已填写贴图正文描述。")
                        return
                if frame is not None:
                    driver.switch_to.default_content()
            except WebDriverException:
                if frame is not None:
                    driver.switch_to.default_content()


def _sort_images_face_first(img_list):
    """确保人脸/特写图片排在首位，以便作为默认封面。"""
    def score(p):
        stem = Path(p).stem.lower()
        if "portrait_face" in stem or "face" in stem:
            return 0
        if any(k in stem for k in ("avatar", "headshot", "close_up", "portrait")):
            return 1
        return 2
    return sorted(img_list, key=score)


def _set_editor_author(driver, author="kenzhao", log=None):
    """设置文章作者（固定为 kenzhao）。"""
    if not author:
        return False
    js_author = """
    var val = arguments[0];
    var cands = Array.from(document.querySelectorAll('#author, input.js_author, input[name="author"]'));
    var el = cands.find(e => e.offsetParent !== null) || cands[0];
    if (el) {
        el.focus();
        var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        nativeSetter.call(el, val.slice(0, 8));
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        el.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: 'o' }));
        el.blur();
        return true;
    }
    return false;
    """
    for frame in [None] + driver.find_elements(By.TAG_NAME, "iframe"):
        try:
            if frame is not None:
                driver.switch_to.frame(frame)
            if driver.execute_script(js_author, author[:8]):
                if frame is not None:
                    driver.switch_to.default_content()
                if log:
                    log(f"已填写文章作者：{author}")
                return True
            if frame is not None:
                driver.switch_to.default_content()
        except Exception:
            if frame is not None:
                driver.switch_to.default_content()
    return False


def _set_editor_original(driver, author="kenzhao", log=None):
    """开启原创声明，自动选择文字原创、填写作者并同意协议。若未实名则平滑跳过。"""
    try:
        clicked = driver.execute_script("""
            var el = document.querySelector('#js_original .js_original_apply') ||
                     document.querySelector('#js_original .setting-group__switch') ||
                     document.querySelector('.js_original_apply');
            if (el) { el.click(); return true; }
            return false;
        """)
        if not clicked:
            return False
        time.sleep(1.5)

        unverified = driver.execute_script("""
            var modal = Array.from(document.querySelectorAll('.weui-desktop-dialog')).find(d => 
                d.innerText.includes('尚未实名') || d.innerText.includes('未设置头像') || d.innerText.includes('未授权使用切换账号')
            );
            if (modal) {
                var cancel = Array.from(modal.querySelectorAll('button, a')).find(b => b.innerText.includes('取消') || b.innerText.includes('我知道了'));
                if (cancel) cancel.click();
                return true;
            }
            return false;
        """)
        if unverified:
            if log:
                log("检测到公众号当前暂未完成原创实名认证，跳过原创声明。")
            return False

        configured = driver.execute_script("""
            var authorName = arguments[0];
            var dlg = Array.from(document.querySelectorAll('.weui-desktop-dialog')).find(d => 
                d.innerText.includes('声明类型') || (d.querySelector('.weui-desktop-dialog__title') && d.querySelector('.weui-desktop-dialog__title').innerText.includes('原创'))
            );
            if (!dlg) return false;

            var textOriLabel = Array.from(dlg.querySelectorAll('.weui-desktop-form__check-label, label, .weui-desktop-radio')).find(l => l.innerText.includes('文字原创'));
            if (textOriLabel) textOriLabel.click();

            // 弹窗内有隐藏的赞赏账户搜索框（同为 input.js_author），必须按 placeholder 精确命中真正的作者框
            var authorInput = dlg.querySelector('input[placeholder="请输入作者"], .js_customerauthor_container input.js_author');
            if (authorInput && authorName) {
                authorInput.focus();
                var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                nativeSetter.call(authorInput, authorName.slice(0, 8));
                authorInput.dispatchEvent(new Event('input', { bubbles: true }));
                authorInput.dispatchEvent(new Event('change', { bubbles: true }));
                authorInput.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: 'o' }));
                authorInput.blur();
            }

            // 协议 checkbox 在 .original_agreement 内；直接取第一个 checkbox 会命中赞赏/快捷转载开关
            var agreeContainer = dlg.querySelector('.original_agreement') ||
                Array.from(dlg.querySelectorAll('label, .weui-desktop-form__check-label')).find(l => l.innerText.includes('同意') && l.querySelector('input[type="checkbox"]'));
            var agreeInput = agreeContainer ? agreeContainer.querySelector('input[type="checkbox"]') : null;
            var agreeLabel = agreeContainer ? (agreeContainer.querySelector('label') || agreeContainer) : null;
            if (agreeInput && !agreeInput.checked) {
                if (agreeLabel) agreeLabel.click();
                if (!agreeInput.checked) {
                    agreeInput.click();
                    agreeInput.checked = true;
                    agreeInput.dispatchEvent(new Event('input', { bubbles: true }));
                    agreeInput.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }

            var confirmBtn = dlg.querySelector('.weui-desktop-dialog__ft .weui-desktop-btn_primary');
            if (!confirmBtn) {
                confirmBtn = Array.from(dlg.querySelectorAll('.weui-desktop-dialog__ft button')).find(b => b.innerText.trim() === '确定');
            }
            if (confirmBtn && !confirmBtn.disabled) {
                confirmBtn.click();
                return true;
            }
            return false;
        """, author)
        if configured:
            time.sleep(1)
            if log:
                log(f"已成功开启原创声明（类型：文字原创，作者：{author}）。")
            return True
    except Exception as e:
        if log:
            log(f"设置原创声明提示：{e}")
    return False


def _set_editor_collection(driver, target_name="#阿ken", log=None):
    """选择合集（文章默认「#阿ken」，贴图默认「OOTD」）。

    合集选择器是一个弹窗 + 下拉框：必须先把下拉展开才能拿到选项
    （选项为 li.select-opt-li），且后台里的合集名是用户自己填的，
    大小写不固定（实测为小写 ootd），因此匹配必须忽略大小写。
    """
    clean_target = target_name.lstrip("#").strip()
    try:
        clicked = driver.execute_script("""
            var el = document.querySelector('#js_article_tags_area .allow_click_opr') ||
                     document.querySelector('#js_article_tags_area label') ||
                     document.querySelector('#js_article_tags_area');
            if (el) { el.click(); return true; }
            return false;
        """)
        if not clicked:
            return False

        # 等「合集」弹窗挂载出来（弹窗是点开后才渲染的）
        _COLLECTION_DLG = """
            return Array.from(document.querySelectorAll('.weui-desktop-dialog')).find(d =>
                d.offsetParent !== null && (d.innerText || '').indexOf('合集') >= 0);
        """
        deadline = time.time() + 8
        while time.time() < deadline:
            if driver.execute_script(_COLLECTION_DLG):
                break
            time.sleep(0.4)

        # 展开「请选择合集」下拉；列表是异步拉取的（面板先显示「加载中...」），
        # 且该接口偶发慢，需要「已展开就等、没展开才点」的多轮重试，避免重复点击把面板关掉。
        def _panel_visible():
            return bool(driver.execute_script("""
                return Array.from(document.querySelectorAll('.select-opt-li, [class*="select-opt"]'))
                             .some(el => el.offsetParent !== null)
                    || Array.from(document.querySelectorAll('*')).some(e =>
                        e.children.length === 0 && (e.innerText || '').trim() === '加载中...' && e.offsetParent !== null);
            """))

        def _open_dropdown():
            return driver.execute_script("""
                var dlg = Array.from(document.querySelectorAll('.weui-desktop-dialog')).find(d =>
                    d.offsetParent !== null && (d.innerText || '').indexOf('合集') >= 0);
                if (!dlg) return false;
                var input = dlg.querySelector('input.weui-desktop-form__input') ||
                            dlg.querySelector('input[placeholder*="合集"]');
                if (input) { input.focus(); input.click(); return true; }
                return false;
            """)

        def _option_texts():
            return driver.execute_script("""
                return Array.from(document.querySelectorAll('.select-opt-li'))
                             .map(el => (el.innerText || '').trim()).filter(t => t);
            """) or []

        opts = []
        for _ in range(4):
            if not _panel_visible():
                _open_dropdown()
            wait_until = time.time() + 5
            while time.time() < wait_until:
                opts = _option_texts()
                if opts:
                    break
                time.sleep(0.5)
            if opts:
                break

        if not opts:
            driver.execute_script("""
                var cancel = Array.from(document.querySelectorAll('.weui-desktop-dialog__ft button'))
                                  .find(b => b.innerText.trim() === '取消');
                if (cancel) cancel.click();
            """)
            if log:
                state = driver.execute_script("""
                    return {
                        dialog: Array.from(document.querySelectorAll('.weui-desktop-dialog'))
                                    .filter(d => d.offsetParent !== null)
                                    .map(d => (d.innerText || '').slice(0, 14).replace(/\\s+/g, '')),
                        optionNodes: document.querySelectorAll('.select-opt-li').length,
                        loading: Array.from(document.querySelectorAll('*')).some(e =>
                            e.children.length === 0 && (e.innerText || '').trim() === '加载中...'),
                        tagsArea: !!document.querySelector('#js_article_tags_area')
                    };
                """)
                log(f"合集下拉未加载出选项，已跳过合集关联。诊断：{state}")
            return False

        selected = driver.execute_script("""
            var target = arguments[0].toLowerCase();
            var all = Array.from(document.querySelectorAll('.select-opt-li'));
            var vis = all.filter(el => el.offsetParent !== null);
            var pool = vis.length ? vis : all;
            var hit = pool.find(el => (el.innerText || '').trim().toLowerCase() === target) ||
                      pool.find(el => (el.innerText || '').trim().toLowerCase().indexOf(target) >= 0);
            if (!hit) return false;
            hit.click();
            return true;
        """, clean_target)
        if not selected:
            driver.execute_script("""
                var cancel = Array.from(document.querySelectorAll('.weui-desktop-dialog__ft button'))
                                  .find(b => b.innerText.trim() === '取消');
                if (cancel) cancel.click();
            """)
            if log:
                log(f"未在公众号后台匹配到合集「{target_name}」，已跳过合集关联。")
            return False

        time.sleep(0.5)
        # 公众号的确认按钮文案是「确认」（不是「确定」）
        confirmed = driver.execute_script("""
            var dlg = Array.from(document.querySelectorAll('.weui-desktop-dialog'))
                          .filter(d => d.offsetParent !== null)[0];
            if (!dlg) return true;
            var btn = dlg.querySelector('.weui-desktop-dialog__ft .weui-desktop-btn_primary') ||
                      Array.from(dlg.querySelectorAll('.weui-desktop-dialog__ft button'))
                           .find(b => b.innerText.trim() === '确认' || b.innerText.trim() === '确定');
            if (btn && !btn.disabled) { btn.click(); return true; }
            return false;
        """)
        time.sleep(1)
        if log:
            log(f"已将内容关联至合集「{target_name}」。" if confirmed
                else f"合集「{target_name}」已选中，但确认按钮未响应。")
        return confirmed
    except Exception as e:
        if log:
            log(f"设置合集提示：{e}")
    return False


def _set_editor_ai_source(driver, log=None):
    """设置创作来源：选择「内容由AI生成」。"""
    try:
        clicked = driver.execute_script("""
            var el = document.querySelector('#js_claim_source_area .allow_click_opr') ||
                     document.querySelector('#js_claim_source_area label') ||
                     document.querySelector('#js_claim_source_area input.js_claim_source');
            if (el) { el.click(); return true; }
            return false;
        """)
        if not clicked:
            return False
        time.sleep(1.5)

        selected = driver.execute_script("""
            var dlg = Array.from(document.querySelectorAll('.weui-desktop-dialog')).find(d =>
                d.offsetParent !== null && (d.innerText || '').indexOf('声明类型') >= 0
            );
            if (!dlg) return false;
            var opt = Array.from(dlg.querySelectorAll('label.weui-desktop-form__check-label')).find(l =>
                (l.innerText || '').indexOf('内容由AI生成') >= 0
            ) || Array.from(dlg.querySelectorAll('*')).find(e =>
                e.children.length === 0 && (e.innerText || '').trim() === '内容由AI生成'
            );
            if (!opt) return false;
            opt.click();
            return true;
        """)
        if not selected:
            driver.execute_script("""
                var b = Array.from(document.querySelectorAll('.weui-desktop-dialog__ft button')).find(x => x.innerText.trim() === '取消');
                if (b) b.click();
            """)
            if log:
                log("未定位到「内容由AI生成」选项，已跳过来源设置。")
            return False

        _AI_DLG_OPEN = """
            return Array.from(document.querySelectorAll('.weui-desktop-dialog')).some(d =>
                d.offsetParent !== null && (d.innerText || '').indexOf('声明类型') >= 0
            );
        """
        # 点确认后弹窗未必立刻关（偶发点击丢失/渲染延迟），多试几轮再判定失败
        for _ in range(3):
            time.sleep(0.5)
            driver.execute_script("""
                var dlg = Array.from(document.querySelectorAll('.weui-desktop-dialog')).find(d =>
                    d.offsetParent !== null && (d.innerText || '').indexOf('声明类型') >= 0
                );
                if (!dlg) return false;
                var btn = dlg.querySelector('.weui-desktop-dialog__ft .weui-desktop-btn_primary') ||
                          Array.from(dlg.querySelectorAll('.weui-desktop-dialog__ft button'))
                               .find(b => b.innerText.trim() === '确认' || b.innerText.trim() === '确定');
                if (btn && !btn.disabled) { btn.click(); return true; }
                return false;
            """)
            wait_until = time.time() + 3
            while time.time() < wait_until:
                if not driver.execute_script(_AI_DLG_OPEN):
                    if log:
                        log("已成功标注创作来源声明：「内容由AI生成」。")
                    return True
                time.sleep(0.5)

        if log:
            log("创作来源弹窗未关闭，创作来源可能未生效。")
        return False
    except Exception as e:
        if log:
            log(f"设置创作来源提示：{e}")
    return False


def _inject_image_captions_in_ueditor(driver, img_list, log=None):
    """在 UEditor 编辑器正文中，为每张图片下方注入中文提示词与艺术风格说明。"""
    try:
        from ..routers.publish import _extract_prompt_text, STYLE_MAPPINGS
    except Exception:
        _extract_prompt_text = lambda p: ""
        STYLE_MAPPINGS = {}

    captions = []
    for p in img_list:
        path_obj = Path(p)
        prompt = _extract_prompt_text(path_obj)
        stem_lower = path_obj.stem.lower()
        matched = [cn for en, cn in STYLE_MAPPINGS.items() if en in stem_lower or en in prompt.lower()]
        style_desc = "、".join(dict.fromkeys(matched)) if matched else "自然光影美学"
        
        prompt_snippet = prompt[:160] + ("..." if len(prompt) > 160 else "") if prompt else "唯美光影人像特写，细腻捕捉真实质感与优雅神韵。"
        caption_html = (
            f"<p style='text-align: center; color: #7f8c8d; font-size: 13px; line-height: 1.6; margin: 8px 0 24px 0;'>"
            f"📷 <strong>画面构想 / 提示词</strong>：{prompt_snippet}<br>"
            f"✨ <strong>艺术风格</strong>：{style_desc}"
            f"</p>"
        )
        captions.append(caption_html)

    # UEditor 只认编辑器命令管线：直接 DOM insertBefore 不会同步内部模型、保存时丢失。
    # 依次尝试「官方 API → 聚焦后 execCommand → 兜底 DOM」，每种方式都**当场校验**
    # 是否真的写进正文，全部失败才返回 False——不再出现"报成功但没生效"。
    js_inject = """
        var captions = arguments[0];
        var out = { injected: 0, method: null, imgCount: 0 };
        var imgs = Array.from(document.body.querySelectorAll('img'));
        out.imgCount = imgs.length;
        if (!imgs.length) return out;

        function hasCaption() {
            return (document.body.textContent || '').indexOf('画面构想') >= 0;
        }
        function placeAfter(img) {
            var r = document.createRange();
            r.setStartAfter(img);
            r.setEndAfter(img);
            var sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(r);
        }
        function pending() {
            return Array.from(document.body.querySelectorAll('img')).filter(function (im) {
                var n = im.nextElementSibling;
                return !(n && (n.textContent || '').indexOf('画面构想') >= 0);
            });
        }

        // 1) UEditor 官方 API（最可靠，走编辑器内部管线）
        try {
            var pue = window.parent && window.parent.UE;
            var ed = null;
            if (pue) {
                if (pue.getEditor) { try { ed = pue.getEditor(); } catch (e) {} }
                if (!ed && pue.instants) { for (var k in pue.instants) { ed = pue.instants[k]; break; } }
            }
            if (ed && ed.execCommand) {
                ed.focus();
                var todo = pending();
                var done = 0;
                for (var i = 0; i < todo.length && i < captions.length; i++) {
                    placeAfter(todo[i]);
                    try { ed.execCommand('inserthtml', captions[i]); done++; } catch (e) {}
                }
                if (done && hasCaption()) { out.injected = done; out.method = 'ue-api'; return out; }
            }
        } catch (e) {}

        // 2) 聚焦文档后走浏览器命令管线（不聚焦时 execCommand 常直接返回 false）
        try {
            window.focus();
            if (document.body.focus) document.body.focus();
            var todo2 = pending();
            var done2 = 0;
            for (var j = 0; j < todo2.length && j < captions.length; j++) {
                placeAfter(todo2[j]);
                if (document.execCommand('insertHTML', false, captions[j])) done2++;
            }
            if (done2 && hasCaption()) { out.injected = done2; out.method = 'execCommand'; return out; }
        } catch (e) {}

        // 3) 兜底：直接改 DOM。编辑态可见、但可能不随保存持久化，由调用方按 method 决定如何提示
        try {
            var todo3 = pending();
            var done3 = 0;
            for (var m = 0; m < todo3.length && m < captions.length; m++) {
                todo3[m].insertAdjacentHTML('afterend', captions[m]);
                done3++;
            }
            if (done3 && hasCaption()) { out.injected = done3; out.method = 'dom'; return out; }
        } catch (e) {}

        return out;
    """

    for frame in driver.find_elements(By.TAG_NAME, "iframe"):
        try:
            driver.switch_to.frame(frame)
            res = driver.execute_script(js_inject, captions) or {}
            driver.switch_to.default_content()
            if res.get("injected"):
                method = res.get("method")
                if log:
                    if method == "dom":
                        log(f"图注已注入 {res['injected']} 处（DOM 兜底方式，可能不随保存持久化，请人工核对）。")
                    else:
                        log(f"已在正文每张图片下方插入中文「提示词与风格说明」（共 {res['injected']} 处，方式：{method}）。")
                return True
        except Exception:
            driver.switch_to.default_content()
    if log:
        log(f"正文图注注入未生效（注入 0 处，正文图片 {len(captions)} 张）。")
    return False


def _publish_images(image_path, title, tags, log, publish_mode="publish", content="", image_paths=None):
    driver = selenium_base.build_driver("wechat_mp", initial_url=MP_URL)
    result = "failed"
    img_list = _sort_images_face_first(image_paths if image_paths else [image_path])
    try:
        if not _open_mp_logged_in(driver, log):
            result = "need_login"
            return result
        token = _get_mp_token(driver)
        # 1. 优先通过微信公众号官方直达 URL 打开独立的「贴图」（图片消息卡片模式，createType=8）
        edit_url = f"https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit_v2&action=edit&isNew=1&type=77&createType=8&lang=zh_CN&token={token}" if token else None
        entered_image_mode = False
        if edit_url:
            _safe_navigate(driver, edit_url, log)
            time.sleep(4)
            if "createType=8" in driver.current_url or "appmsg_edit" in driver.current_url:
                entered_image_mode = True

        # 2. 备用方式：从公众号首页「新的创作」菜单直接点击「贴图」入口
        if not entered_image_mode:
            clicked_tietu = driver.execute_script("""
                var el = Array.from(document.querySelectorAll('.new-creation__menu-item, .new-creation__menu-title, .new-creation__menu-content')).find(e => e.innerText.trim() === '贴图');
                if (el) { el.click(); return true; }
                return false;
            """)
            if clicked_tietu:
                time.sleep(3)
                if len(driver.window_handles) > 1:
                    driver.switch_to.window(driver.window_handles[-1])
                entered_image_mode = True
            elif _click_text_button(driver, ["贴图", "图片消息", "新建图片消息"], log):
                time.sleep(3)
                if len(driver.window_handles) > 1:
                    driver.switch_to.window(driver.window_handles[-1])
                entered_image_mode = True

        if not entered_image_mode:
            log("未能进入贴图草稿编辑器，请人工在浏览器窗口中进入。")
            result = _wait_manual_finish(driver, log, "进入贴图编辑器并存草稿")
            return result

        file_input = _find_file_input_anywhere(driver)
        if file_input is None:
            _click_text_button(driver, ["选择图片", "上传图片", "本地上传", "图片"], log)
            time.sleep(2)
            file_input = _find_file_input_anywhere(driver)

        if file_input is None:
            log("未定位到图片上传控件，请人工上传。")
            result = _wait_manual_finish(driver, log, "上传图片并存草稿")
            return result
        paths_str = "\n".join(str(Path(p).resolve()) for p in img_list)
        file_input.send_keys(paths_str)
        log(f"已注入组合图片共 {len(img_list)} 张。")
        time.sleep(3 + min(len(img_list), 5))
        _fill_editor_title(driver, title, log)
        _set_editor_author(driver, "kenzhao", log)
        tag_str = " ".join(f"#{t.strip()}" for t in (tags or []) if t.strip() and f"#{t.strip()}" not in (content or ""))
        full_content = f"{content}\n\n{tag_str}".strip() if tag_str else (content or "")
        _fill_image_post_content(driver, full_content, log)

        # 贴图合集选择「OOTD」
        _set_editor_collection(driver, target_name="OOTD", log=log)
        # 创作来源标注「内容由AI生成」
        _set_editor_ai_source(driver, log=log)

        if publish_mode == "manual":
            result = _wait_manual_finish(driver, log, "人工确认并保存")
            return result

        if publish_mode == "draft":
            clicked = _click_text_button(
                driver, ["保存为草稿", "存为草稿", "保存到草稿箱", "保存"], log,
                exclude_texts=["群发", "发表", "保存并群发"])
            if clicked:
                log("已自动点击「保存为草稿」，等待保存确认...")
                if _wait_draft_save_success(driver, log, timeout=40, title=title):
                    log("贴图（图片消息）已全自动保存到公众号草稿箱！")
                    result = "success"
                    return result
            log("自动存草稿未在预期时间内检测到完成，平滑降级为人工确认。")
            result = _wait_manual_finish(driver, log, "确认图片消息保存")
            return result
        else:
            _click_text_button(driver, ["保存并群发", "保存", "发表"], log)
            result = _wait_manual_finish(driver, log, "确认图片消息并发表")
            return result
    finally:
        if result != "need_login":
            selenium_base.release_driver(driver, log)


# ---------------------------------------------------------------------------
# 图文文章（图片模式：标题 + 正文贴图 + 封面 → 保存草稿/发表）
# ---------------------------------------------------------------------------

def _publish_article(image_path, title, tags, log, publish_mode="publish", content="", image_paths=None):
    driver = selenium_base.build_driver("wechat_mp", initial_url=MP_URL)
    result = "failed"
    img_list = _sort_images_face_first(image_paths if image_paths else [image_path])
    try:
        if not _open_mp_logged_in(driver, log):
            result = "need_login"
            return result
        token = _get_mp_token(driver)
        edit_url = f"https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit_v2&action=edit&isNew=1&type=77&lang=zh_CN&token={token}" if token else ARTICLE_EDIT_URL
        _safe_navigate(driver, edit_url, log)
        time.sleep(4)
        if "appmsg" not in driver.current_url and "edit" not in driver.current_url:
            clicked_art = driver.execute_script("""
                var el = Array.from(document.querySelectorAll('.new-creation__menu-item, .new-creation__menu-title, .new-creation__menu-content')).find(e => e.innerText.trim() === '文章');
                if (el) { el.click(); return true; }
                return false;
            """)
            if clicked_art:
                time.sleep(3)
                if len(driver.window_handles) > 1:
                    driver.switch_to.window(driver.window_handles[-1])
            elif not _click_text_button(driver, ["文章", "图文消息", "写新图文", "新的创作"], log):
                log("未能进入图文文章编辑器，请人工进入后完成。")
                result = _wait_manual_finish(driver, log, "进入图文文章编辑器")
                return result
        # 1. 填写标题与作者（固定为 kenzhao）
        _fill_editor_title(driver, title, log)
        _set_editor_author(driver, "kenzhao", log)

        # 2. 填入正文开头导语与标签描述
        tag_str = " ".join(f"#{t.strip()}" for t in (tags or []) if t.strip() and f"#{t.strip()}" not in (content or ""))
        full_content = f"{content}\n\n{tag_str}".strip() if tag_str else (content or "")
        _fill_article_body_content(driver, full_content, log)

        # 3. 正文插入多张图片
        body_inserted = False
        try:
            driver.switch_to.frame(driver.find_element(By.XPATH, '//iframe[contains(@id,"ueditor") or contains(@class,"edui")]'))
            driver.find_element(By.TAG_NAME, "body").click()
            driver.switch_to.default_content()
        except WebDriverException:
            driver.switch_to.default_content()
        if _click_text_button(driver, ["图片"], log):
            time.sleep(2)
            file_input = _find_file_input_anywhere(driver)
            if file_input is not None:
                paths_str = "\n".join(str(Path(p).resolve()) for p in img_list)
                file_input.send_keys(paths_str)
                body_inserted = True
                log(f"已向文章正文上传并注入 {len(img_list)} 张图片。")
                time.sleep(4 + min(len(img_list), 6))
                _click_text_button(driver, ["确定", "完成", "下一步", "插入"], log)
        if not body_inserted:
            log("正文插图未自动化成功，请人工在编辑器中插入图片。")

        # 4. 在正文中为每张图片下方注入中文提示词与艺术风格说明
        time.sleep(1.5)
        _inject_image_captions_in_ueditor(driver, img_list, log)

        # 5. 封面选择（默认优先选取人脸图片）
        if _click_text_button(driver, ["从正文选择"], log):
            time.sleep(2)
            # 点击首张候选图片（首图已由 _sort_images_face_first 排序为人脸图）
            driver.execute_script("""
                var candidates = Array.from(document.querySelectorAll('.select-cover__dialog img, .weui-desktop-dialog img, .weui-desktop-dialog .img-crop, .frame-item'));
                if (candidates.length > 0) {
                    candidates[0].click();
                }
            """)
            time.sleep(1)
            _click_text_button(driver, ["确定", "下一步", "完成"], log)
            time.sleep(1)
            _click_text_button(driver, ["完成", "确定"], log)
            log("已设置文章封面（默认使用人脸图片）。")
        else:
            log("未自动设置封面（公众号文章必须有封面，请人工补充）。")

        # 6. 设置原创声明（声明类型：文字原创，作者：kenzhao）
        _set_editor_original(driver, author="kenzhao", log=log)

        # 7. 文章合集选择「#阿ken」
        _set_editor_collection(driver, target_name="#阿ken", log=log)

        # 8. 创作来源声明选择「内容由AI生成」
        _set_editor_ai_source(driver, log=log)

        if publish_mode == "manual":
            result = _wait_manual_finish(driver, log, "人工确认并保存")
            return result

        if publish_mode == "draft":
            clicked = _click_text_button(
                driver, ["保存为草稿", "存为草稿", "保存到草稿箱", "保存"], log,
                exclude_texts=["群发", "发表", "保存并群发"])
            if clicked:
                log("已自动点击「保存为草稿」，等待保存确认...")
                if _wait_draft_save_success(driver, log, timeout=40, title=title):
                    log("图文文章已全自动保存到公众号草稿箱！")
                    result = "success"
                    return result
            log("自动存草稿未在预期时间内检测到完成，平滑降级为人工确认。")
            result = _wait_manual_finish(driver, log, "确认文章保存为草稿")
            return result
        else:
            if _click_text_button(driver, ["保存并群发", "发表"], log):
                log("已点击发表/群发，若弹出管理员确认或二维码请在窗口中完成。")
            else:
                log("未找到发表按钮，请人工发表。")
            result = _wait_manual_finish(driver, log, "完成发表确认")
            return result
    finally:
        if result != "need_login":
            selenium_base.release_driver(driver, log)


def _dismiss_mp_popups(driver, log=None):
    """自动关闭公众号编辑器的常见引导、版本升级、恢复未保存内容等阻断性弹窗。"""
    try:
        driver.execute_script("""
            var dialogs = Array.from(document.querySelectorAll('.weui-desktop-dialog, .weui-desktop-modal, .weui-desktop-popover, [role="dialog"]'));
            for (var dlg of dialogs) {
                var text = dlg.innerText || '';
                // 1. 发现未保存的内容
                if (text.includes('未保存') || text.includes('恢复') || text.includes('继续编辑')) {
                    var okBtn = Array.from(dlg.querySelectorAll('button, a')).find(b => 
                        b.innerText.includes('继续编辑') || b.innerText.includes('重新编辑') || b.innerText.includes('确定') || b.innerText.includes('取消')
                    );
                    if (okBtn) okBtn.click();
                }
                // 2. 新功能引导或版本提示
                if (text.includes('新版') || text.includes('上线') || text.includes('引导') || text.includes('功能升级') || text.includes('小贴士')) {
                    var closeBtn = Array.from(dlg.querySelectorAll('button, a')).find(b => 
                        b.innerText.includes('我知道了') || b.innerText.includes('跳过') || b.innerText.includes('完成') || b.innerText.includes('确定')
                    );
                    if (closeBtn) closeBtn.click();
                }
            }
        """)
    except Exception:
        pass


def _fill_editor_title(driver, title, log):
    if not title:
        return
    _dismiss_mp_popups(driver, log)
    # 1. 优先使用 JavaScript 直接为微信公众号编辑器的标题控件赋值与分发事件（绕过 is_displayed 样式隐藏限制，并支持多轮挂载重试）
    js_set_title = """
    var val = arguments[0];
    // 可见编辑器优先：标题真正被保存的是可见控件，#title 只是隐藏镜像域。
    // 之前把 #title 排在最前，导致只写了隐藏域、界面标题框依旧空白。
    var visibleSelectors = [
        '#js_title_main .ProseMirror',
        'div[contenteditable="true"][data-placeholder*="标题"]',
        '.title_editor [contenteditable="true"]',
        'input[placeholder*="标题"]',
        'textarea[placeholder*="标题"]',
        'textarea.js_article_title',
        'textarea.js_title'
    ];
    var el = null;
    for (var i = 0; i < visibleSelectors.length; i++) {
        var c = document.querySelector(visibleSelectors[i]);
        if (c && c.offsetParent !== null) { el = c; break; }
    }
    if (!el) { el = document.querySelector('#title') || document.querySelector('input.js_title'); }
    if (!el) return false;

    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
        el.focus();
        var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        setter.call(el, val);
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        el.blur();
    } else {
        // ProseMirror 只认浏览器真实输入管线，直接写 innerText 不会同步内部模型
        el.focus();
        document.execCommand('selectAll', false, null);
        document.execCommand('insertText', false, val);
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.blur();
    }
    var hiddenTitle = document.querySelector('#title');
    if (hiddenTitle && hiddenTitle !== el) {
        hiddenTitle.value = val;
        hiddenTitle.dispatchEvent(new Event('input', { bubbles: true }));
        hiddenTitle.dispatchEvent(new Event('change', { bubbles: true }));
    }
    return true;
    """
    for attempt in range(8):
        _dismiss_mp_popups(driver, log)
        for frame in [None] + driver.find_elements(By.TAG_NAME, "iframe"):
            try:
                if frame is not None:
                    driver.switch_to.frame(frame)
                success = driver.execute_script(js_set_title, title[:64])
                if frame is not None:
                    driver.switch_to.default_content()
                if success:
                    log("已成功填写文章标题。")
                    return
            except Exception:
                if frame is not None:
                    driver.switch_to.default_content()
        time.sleep(0.7)

    # 2. 备用常规交互
    for xpath in ('//input[@id="title"]', '//textarea[@id="title"]', '//input[contains(@placeholder,"标题")]', '//div[@contenteditable="true" and contains(@data-placeholder,"标题")]', '//input[contains(@class,"weui-desktop-form__input")]'):
        for frame in [None] + driver.find_elements(By.TAG_NAME, "iframe"):
            try:
                if frame is not None:
                    driver.switch_to.frame(frame)
                els = driver.find_elements(By.XPATH, xpath)
                for el in els:
                    try:
                        el.click()
                        el.clear()
                        el.send_keys(title[:64])
                        if frame is not None:
                            driver.switch_to.default_content()
                        log("已填写文章标题。")
                        return
                    except Exception:
                        pass
                if frame is not None:
                    driver.switch_to.default_content()
            except WebDriverException:
                if frame is not None:
                    driver.switch_to.default_content()
    log("未定位到标题输入框，请人工填写标题。")

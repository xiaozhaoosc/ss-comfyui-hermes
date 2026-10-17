"""原创声明弹窗定位逻辑的 DOM 级验证。

微信弹窗 DOM 由线上抓包复刻：赞赏/快捷转载 checkbox 在协议 checkbox 之前，
且存在隐藏的赞赏账户搜索框（同为 input.js_author）。旧实现会误命中这两个，
本测试用真实 Chrome 跑 `_set_editor_original`，断言作者与协议都填到正确元素上。

用法：
    venv/Scripts/python.exe tools/asset_manager/test_original_dialog.py
"""
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from backend.publishers.wechat_mp import _set_editor_original

MOCK_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>原创声明 mock</title>
<style>
  .weui-desktop-dialog { display: none; border: 1px solid #999; padding: 8px; }
  .weui-desktop-dialog.open { display: block; }
</style></head><body>
<div id="js_original"><a class="js_original_apply" onclick="openDlg()">声明原创</a></div>

<div class="weui-desktop-dialog" id="dlg">
  <div class="weui-desktop-dialog__title">原创声明</div>
  <div class="weui-desktop-dialog__bd">
    <p>声明类型</p>
    <label class="weui-desktop-form__check-label">赞赏<input type="checkbox" id="cb_appreciate"></label>
    <label class="weui-desktop-form__check-label">快捷转载<input type="checkbox" id="cb_reprint"></label>
    <label class="weui-desktop-form__check-label">文字原创<input type="radio" name="ori" id="rb_text"></label>
    <input class="js_author" placeholder="请输入赞赏账户名称，进行查找" style="display:none">
    <div class="js_customerauthor_container">
      <input class="js_author" placeholder="请输入作者" id="author_real">
      <em class="frm_counter">0/8</em>
    </div>
    <div class="original_agreement">
      <label><input type="checkbox" id="cb_agree">我已阅读并同意《微信公众平台原创声明及相关功能使用协议》</label>
    </div>
    <p id="err" style="color:red"></p>
  </div>
  <div class="weui-desktop-dialog__ft">
    <button class="weui-desktop-btn_primary" id="btn_ok">确定</button>
  </div>
</div>

<script>
function openDlg() { document.getElementById('dlg').classList.add('open'); }
window.__submitted = false;
var ai = document.getElementById('author_real');
ai.addEventListener('input', function () {
  document.querySelector('.frm_counter').textContent = ai.value.length + '/8';
});
document.getElementById('btn_ok').addEventListener('click', function () {
  if (!ai.value) { document.getElementById('err').textContent = '作者不能为空且不超过8个字'; return; }
  if (!document.getElementById('cb_agree').checked) { document.getElementById('err').textContent = '请阅读并同意协议'; return; }
  window.__submitted = true;
  document.getElementById('dlg').classList.remove('open');
});
</script>
</body></html>"""


# 打补丁前的旧选择逻辑，用作对照组：必须命中错误元素，否则说明 mock 没有区分度
OLD_JS = """
var dlg = Array.from(document.querySelectorAll('.weui-desktop-dialog')).find(d =>
    d.innerText.includes('声明类型') || (d.querySelector('.weui-desktop-dialog__title') && d.querySelector('.weui-desktop-dialog__title').innerText.includes('原创'))
);
if (!dlg) return false;
var authorInput = dlg.querySelector('input[placeholder*="作者"], input.js_author, input[name="author"]');
if (authorInput) {
    authorInput.value = 'kenzhao';
    authorInput.dispatchEvent(new Event('input', { bubbles: true }));
    authorInput.dispatchEvent(new Event('change', { bubbles: true }));
}
var agreeBox = dlg.querySelector('input[type="checkbox"]');
if (agreeBox && !agreeBox.checked) { agreeBox.click(); }
var confirmBtn = Array.from(dlg.querySelectorAll('button')).find(b => b.innerText.trim() === '确定');
if (confirmBtn) { confirmBtn.click(); return true; }
return false;
"""


def _probe(driver):
    """读取 mock 页面上各元素的最终状态。"""
    return driver.execute_script("""
        return {
            author_real: document.getElementById('author_real').value,
            author_hidden: document.querySelector('input[placeholder*="赞赏账户"]').value,
            counter: document.querySelector('.frm_counter').textContent,
            agree: document.getElementById('cb_agree').checked,
            appreciate: document.getElementById('cb_appreciate').checked,
            reprint: document.getElementById('cb_reprint').checked,
            text_ori: document.getElementById('rb_text').checked,
            submitted: window.__submitted,
            err: document.getElementById('err').textContent,
            dlg_open: document.getElementById('dlg').classList.contains('open')
        };
    """)


def main():
    profile = tempfile.mkdtemp(prefix="wechat_original_test_")
    html_path = os.path.join(profile, "mock.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(MOCK_HTML)

    # 本机 HTTP_PROXY 会劫持 Chrome 的全部请求（连 file:// 也走代理），必须显式关掉
    for var in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        os.environ.pop(var, None)

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--no-proxy-server")
    opts.add_argument(f"--user-data-dir={profile}")
    driver = webdriver.Chrome(options=opts)

    failures = []
    try:
        url = "file:///" + html_path.replace("\\", "/")

        def check(label, actual, expected):
            good = actual == expected
            print(f"  [{'PASS' if good else 'FAIL'}] {label}: {actual!r}")
            if not good:
                failures.append(f"{label}: 期望 {expected!r}，实际 {actual!r}")

        driver.get(url)
        print("对照组（补丁前的旧选择逻辑，期望全部失败）：")
        driver.execute_script("openDlg()")
        driver.execute_script(OLD_JS)
        old_state = _probe(driver)
        check("旧逻辑未填真作者框", old_state["author_real"], "")
        check("旧逻辑误勾赞赏开关", old_state["appreciate"], True)
        check("旧逻辑漏勾协议", old_state["agree"], False)
        check("旧逻辑提交失败", old_state["submitted"], False)

        driver.get(url)
        logs = []
        ok = _set_editor_original(driver, author="kenzhao", log=logs.append)
        state = _probe(driver)

        print("\n原创声明弹窗 DOM 级验证：")
        check("函数返回 True", ok, True)
        check("真作者框已填", state["author_real"], "kenzhao")
        check("隐藏赞赏框未被填", state["author_hidden"], "")
        check("计数器已刷新", state["counter"], "7/8")
        check("协议 checkbox 已勾选", state["agree"], True)
        check("赞赏开关未被误勾", state["appreciate"], False)
        check("快捷转载开关未被误勾", state["reprint"], False)
        check("文字原创已选中", state["text_ori"], True)
        check("无校验报错", state["err"], "")
        check("确定已提交并关窗", state["submitted"], True)
        check("弹窗已关闭", state["dlg_open"], False)
        for line in logs:
            print(f"    log> {line}")
    finally:
        driver.quit()

    if failures:
        print("\n失败项：")
        for f in failures:
            print("  - " + f)
        return 1
    print("\n全部通过：新逻辑命中正确元素，对照组确认旧逻辑会失败。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

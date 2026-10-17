# -*- coding: utf-8 -*-
"""文章正文图注注入方案对照探针：找出为什么 `注入 0 处`。

在真正的 UEditor 正文 iframe 里依次尝试 4 种注入方式，报告哪种生效。

用法：venv/Scripts/python.exe tools/asset_manager/_probe_caption.py
"""
import importlib
import json
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
for k in list(os.environ):
    if k.lower().endswith("_proxy"):
        os.environ.pop(k)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _cdp_probe

mp = importlib.import_module("backend.publishers.wechat_mp")
sb = importlib.import_module("backend.publishers.selenium_base")

DIR = Path(r"D:\ai_projects\ComfyUI\output\2026-10-16\flow_images")
IMAGES = [DIR / "char_cen_youqing_2204_01_01_front_9_16_220706_1.png",
          DIR / "char_cen_youqing_2204_01_07_portrait_face_9_16_221805_1.png"]

HTML = ("<p style='text-align:center;color:#7f8c8d;font-size:13px;'>"
        "📷 <strong>画面构想 / 提示词</strong>：探针测试用说明<br>"
        "✨ <strong>艺术风格</strong>：自然光影美学</p>")

JS_LIST_FRAMES = """return (function(){
  return Array.from(document.querySelectorAll('iframe')).map(function(f, i){
    var doc = null;
    try { doc = f.contentDocument; } catch (e) {}
    var body = doc && doc.body;
    return { i: i, id: f.id || '', cls: (f.className || '').toString().slice(0, 50),
             reachable: !!doc, imgs: body ? body.querySelectorAll('img').length : -1,
             designMode: doc ? doc.designMode : null,
             bodyEditable: body ? body.getAttribute('contenteditable') : null };
  });
})()"""

# 在同一 frame 里依次试 4 种方式
JS_TRY = """return (function(html){
  var out = {};
  var imgs = Array.from(document.body.querySelectorAll('img'));
  out.imgCount = imgs.length;
  if (!imgs.length) return out;
  var img = imgs[0];

  function placeRange() {
    var r = document.createRange();
    r.setStartAfter(img); r.setEndAfter(img);
    var sel = window.getSelection();
    sel.removeAllRanges(); sel.addRange(r);
  }

  // A：先聚焦再 execCommand
  try {
    window.focus();
    placeRange();
    out.A_focusExec = document.execCommand('insertHTML', false, html);
    if (out.A_focusExec) return out;
  } catch (e) { out.A_err = String(e); }

  // B：不聚焦直接 execCommand
  try {
    placeRange();
    out.B_noFocusExec = document.execCommand('insertHTML', false, html);
    if (out.B_noFocusExec) return out;
  } catch (e) { out.B_err = String(e); }

  // C：走 UEditor 自己的 API
  try {
    var w = window.parent && window.parent.UE;
    var ed = null;
    if (w && w.getEditor) { ed = w.getEditor(); }
    if (!ed && w && w.instants) { for (var k in w.instants) { ed = w.instants[k]; break; } }
    out.ueFound = !!ed;
    if (ed) {
      ed.focus();
      ed.execCommand('inserthtml', html);
      out.C_ueApi = true;
      return out;
    }
  } catch (e) { out.C_err = String(e); }

  // D：暴力 DOM（不保证保存后还在，仅作对照）
  try {
    img.insertAdjacentHTML('afterend', html);
    out.D_dom = true;
  } catch (e) { out.D_err = String(e); }

  return out;
})"""


def main():
    for port in (9527, 9528):
        _cdp_probe.close_unresponsive_tabs(port, verbose=True)

    driver = sb.build_driver("wechat_mp", initial_url=mp.MP_URL)
    try:
        mp._open_mp_logged_in(driver, lambda m: print("  log>", m))
        token = mp._get_mp_token(driver)
        url = (f"https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit_v2"
               f"&action=edit&isNew=1&type=77&lang=zh_CN&token={token}")
        mp._safe_navigate(driver, url, lambda m: print("  log>", m))
        time.sleep(4)

        print("\n[1] 上传图片到正文")
        img_list = mp._sort_images_face_first(IMAGES)
        mp._click_text_button(driver, ["图片"], print)
        time.sleep(2)
        fi = mp._find_file_input_anywhere(driver)
        if fi is None:
            print("  未找到上传控件")
            return 1
        fi.send_keys("\n".join(str(Path(p).resolve()) for p in img_list))
        time.sleep(8)
        mp._click_text_button(driver, ["确定", "完成", "下一步", "插入"], print)
        time.sleep(4)

        print("\n[2] iframe 清单")
        frames = driver.execute_script(JS_LIST_FRAMES)
        print(json.dumps(frames, ensure_ascii=False, indent=1))

        print("\n[3] 在有图的 frame 里试 4 种注入方式")
        for fr in frames:
            if fr["imgs"] <= 0:
                continue
            print(f"  -> 进入 iframe[{fr['i']}] id={fr['id']} imgs={fr['imgs']}")
            frame_els = driver.find_elements("tag name", "iframe")
            driver.switch_to.frame(frame_els[fr["i"]])
            try:
                res = driver.execute_script(JS_TRY, HTML)
                print("  结果:", json.dumps(res, ensure_ascii=False))
                after = driver.execute_script(
                    "return {hasCaption: (document.body.textContent||'').indexOf('画面构想')>=0,"
                    " imgs: document.body.querySelectorAll('img').length}")
                print("  注入后:", json.dumps(after, ensure_ascii=False))
            finally:
                driver.switch_to.default_content()
            break
    finally:
        try:
            driver.quit()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

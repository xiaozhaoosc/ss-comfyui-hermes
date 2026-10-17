# -*- coding: utf-8 -*-
"""图文文章发布流程的分步计时诊断，用于定位哪一步卡住。

用法：venv/Scripts/python.exe tools/asset_manager/_e2e_article_trace.py
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

# 注意：backend.publishers.__init__ 用 `from .wechat_mp import publish as wechat_mp` 覆盖了
# 子模块名，因此不能用 `import backend.publishers.wechat_mp as mp`，必须直接导入符号。
mp = importlib.import_module("backend.publishers.wechat_mp")
sb = importlib.import_module("backend.publishers.selenium_base")

DIR = Path(r"D:\ai_projects\ComfyUI\output\2026-10-16\flow_images")
IMAGES = [
    DIR / "char_cen_youqing_2204_01_07_portrait_face_9_16_221805_1.png",
    DIR / "char_cen_youqing_2204_01_01_front_9_16_220706_1.png",
    DIR / "char_cen_youqing_2204_01_02_three_quarter_9_16_220904_1.png",
]


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _count_body_imgs(driver):
    """统计正文（ueditor iframe）里的图片数量，用于确认图片真的插进去了。"""
    return driver.execute_script("""return (function(){
      var n = 0;
      Array.from(document.querySelectorAll('iframe')).forEach(function(f){
        try { if (f.contentDocument) n += f.contentDocument.querySelectorAll('img').length; } catch (e) {}
      });
      var body = document.querySelector('.edui-body-container');
      return { bodyImgs: body ? body.querySelectorAll('img').length : -1, iframeImgs: n };
    })()""")


def _dump_body(driver):
    """把所有 iframe 的图片数与可编辑性列出来，定位真正的 UEditor 正文 frame。"""
    out = driver.execute_script("""return (function(){
      return Array.from(document.querySelectorAll('iframe')).map(function(f, i){
        var doc = null;
        try { doc = f.contentDocument; } catch (e) {}
        var body = doc && doc.body;
        return { i: i, id: f.id || '', cls: (f.className || '').toString().slice(0, 40),
                 reachable: !!doc, imgs: body ? body.querySelectorAll('img').length : -1,
                 editable: body ? (body.getAttribute('contenteditable') === 'true' || doc.designMode === 'on') : false,
                 designMode: doc ? doc.designMode : null };
      });
    })()""")
    print("  所有 iframe:", json.dumps(out, ensure_ascii=False))
    detail = driver.execute_script("""return (function(){
      var frames = Array.from(document.querySelectorAll('iframe'));
      for (var i = 0; i < frames.length; i++) {
        var doc = null;
        try { doc = frames[i].contentDocument; } catch (e) {}
        if (!doc || !doc.body || !doc.body.querySelectorAll('img').length) continue;
        var imgs = Array.from(doc.body.querySelectorAll('img'));
        return { frameIndex: i, imgCount: imgs.length,
                 captionAfterImg: imgs.map(function(im){
                   var n = im.nextElementSibling;
                   return n ? (n.textContent || '').replace(/\\s+/g, ' ').slice(0, 60) : null;
                 }),
                 hasCaptionText: (doc.body.textContent || '').indexOf('画面构想') >= 0,
                 bodyText: (doc.body.textContent || '').replace(/\\s+/g, ' ').slice(0, 200) };
      }
      return null;
    })()""")
    print("  正文结构:", json.dumps(detail, ensure_ascii=False, indent=1))


def step(label, fn):
    t0 = time.time()
    try:
        out = fn()
        log(f"{label} 完成，用时 {time.time() - t0:.1f}s")
        return out
    except Exception as e:
        log(f"{label} 失败（{time.time() - t0:.1f}s）：{type(e).__name__} {str(e)[:160]}")
        raise


def main():
    driver = step("build_driver", lambda: sb.build_driver("wechat_mp", initial_url=mp.MP_URL))
    try:
        step("_open_mp_logged_in", lambda: mp._open_mp_logged_in(driver, log))
        token = step("_get_mp_token", lambda: mp._get_mp_token(driver))
        edit_url = (f"https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit_v2"
                    f"&action=edit&isNew=1&type=77&lang=zh_CN&token={token}")
        step("driver.get(编辑页)", lambda: driver.get(edit_url))
        step("_fill_editor_title", lambda: mp._fill_editor_title(driver, "分步诊断测试标题", log))
        step("_set_editor_author", lambda: mp._set_editor_author(driver, "kenzhao", log))
        step("_fill_article_body_content", lambda: mp._fill_article_body_content(driver, "正文诊断内容。", log))

        img_list = step("_sort_images_face_first", lambda: mp._sort_images_face_first(IMAGES))
        step("点击「图片」", lambda: mp._click_text_button(driver, ["图片"], log))
        file_input = step("定位 file input", lambda: mp._find_file_input_anywhere(driver))

        def _upload():
            file_input.send_keys("\n".join(str(Path(p).resolve()) for p in img_list))
            time.sleep(6)

        step("上传正文图片", _upload)
        step("点击插入", lambda: mp._click_text_button(driver, ["确定", "完成", "下一步", "插入"], log))
        step("_inject_image_captions_in_ueditor",
             lambda: mp._inject_image_captions_in_ueditor(driver, img_list, log))
        _dump_body(driver)
        driver.save_screenshot(r"D:\ai_projects\ComfyUI\output\2026-10-17\tietu_debug\06_article_body.png")
        step("封面-从正文选择", lambda: mp._click_text_button(driver, ["从正文选择"], log))
        step("_set_editor_original", lambda: mp._set_editor_original(driver, author="kenzhao", log=log))
        step("_set_editor_collection", lambda: mp._set_editor_collection(driver, target_name="#阿ken", log=log))
        step("_set_editor_ai_source", lambda: mp._set_editor_ai_source(driver, log=log))
    finally:
        try:
            driver.quit()
        except Exception:
            pass
    print("\n诊断结束（未保存草稿）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

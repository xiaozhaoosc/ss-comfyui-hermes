# -*- coding: utf-8 -*-
"""贴图发布流程字段级审计：标题/描述/合集/创作来源 是否真正生效。

不保存草稿，只在编辑器里跑一遍并抓取每步的真实 DOM 状态。

用法：venv/Scripts/python.exe tools/asset_manager/_audit_tietu_fields.py
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

mp = importlib.import_module("backend.publishers.wechat_mp")
sb = importlib.import_module("backend.publishers.selenium_base")

DIR = Path(r"D:\ai_projects\ComfyUI\output\2026-10-16\flow_images")
IMAGES = [DIR / "char_cen_youqing_2204_01_01_front_9_16_220706_1.png",
          DIR / "char_cen_youqing_2204_01_02_three_quarter_9_16_220904_1.png",
          DIR / "char_cen_youqing_2204_01_03_side_profile_9_16_221103_1.png",
          DIR / "char_cen_youqing_2204_01_07_portrait_face_9_16_221805_1.png",
          DIR / "char_cen_youqing_2204_01_08_portrait_45deg_9_16_221920_1.png"]
OUT = Path(r"D:\ai_projects\ComfyUI\output\2026-10-17\tietu_debug")
OUT.mkdir(parents=True, exist_ok=True)

TITLE = "岑幼清 ｜ 新中式清雅温婉写真集"
CONTENT = "✨ 【光影与视觉精选】\n本期带来「岑幼清」的精选视觉呈现。\n\n#AI摄影 #光影美学 #岑幼清 #新中式清雅温婉"

# 编辑器左侧设置面板的字段行文本（合集 / 创作来源 等）
JS_PANEL = """return (function(){
  var keys = ['合集', '创作来源', '赞赏', '留言', '位置', '链接', '平台推荐'];
  var out = {};
  keys.forEach(function(k){
    var row = Array.from(document.querySelectorAll('li,div,p')).find(function(e){
      var t = (e.innerText || '').replace(/\\s+/g, '');
      return t.indexOf(k) >= 0 && t.length < 90;
    });
    out[k] = row ? (row.innerText || '').replace(/\\s+/g, ' ').slice(0, 70) : null;
  });
  return out;
})()"""

JS_FIELDS = """return (function(){
  var title = document.querySelector('#title, .js_title, textarea[placeholder*="标题"]');
  var desc = document.querySelector('.js_desc, [placeholder*="描述信息"], .edui-body-container, [contenteditable="true"]');
  return {
    titleValue: title ? title.value : null,
    titlePlaceholder: title ? title.placeholder : null,
    descText: desc ? (desc.innerText || desc.value || '').slice(0, 200) : null,
    descPlaceholder: desc ? desc.placeholder : null,
    imageCount: document.querySelectorAll('.image-selector img').length,
    counter: (document.body.innerText.match(/(\\d+)\\/(\\d+)/) || [])[0]
  };
})()"""


def js(d, expr):
    return d.execute_script(expr)


def main():
    # 僵尸标签页会让 build_driver 建会话无限挂起，跑之前先自动清理
    import _cdp_probe
    for port in (9527, 9528):
        kept, closed = _cdp_probe.close_unresponsive_tabs(port, verbose=True)
        print(f"端口 {port} 标签页清理：保留 {kept}，关闭 {closed}")

    driver = sb.build_driver("wechat_mp", initial_url=mp.MP_URL)
    try:
        mp._open_mp_logged_in(driver, lambda m: print("  log>", m))
        token = mp._get_mp_token(driver)
        driver.get(f"https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit_v2"
                   f"&action=edit&isNew=1&type=77&createType=8&lang=zh_CN&token={token}")
        time.sleep(5)

        print("\n[0] 初始字段:", json.dumps(js(driver, JS_FIELDS), ensure_ascii=False))

        fi = mp._find_file_input_anywhere(driver)
        fi.send_keys("\n".join(str(p) for p in IMAGES))
        time.sleep(10)
        print("[1] 传图后:", json.dumps(js(driver, JS_FIELDS), ensure_ascii=False))

        mp._fill_editor_title(driver, TITLE, print)
        time.sleep(1)
        print("[2] 填标题后:", json.dumps(js(driver, JS_FIELDS), ensure_ascii=False))

        mp._set_editor_author(driver, "kenzhao", print)
        time.sleep(1)
        print("[3] 填作者后:", json.dumps(js(driver, JS_FIELDS), ensure_ascii=False))

        mp._fill_image_post_content(driver, CONTENT, print)
        time.sleep(1)
        print("[4] 填描述后:", json.dumps(js(driver, JS_FIELDS), ensure_ascii=False))
        driver.save_screenshot(str(OUT / "a1_title_desc.png"))

        print("\n[5] 合集（OOTD）:")
        mp._set_editor_collection(driver, target_name="OOTD", log=print)
        time.sleep(2)
        print("    面板:", json.dumps(js(driver, JS_PANEL), ensure_ascii=False))
        driver.save_screenshot(str(OUT / "a2_collection.png"))

        print("\n[6] 创作来源（内容由AI生成）:")
        mp._set_editor_ai_source(driver, log=print)
        time.sleep(2)
        print("    面板:", json.dumps(js(driver, JS_PANEL), ensure_ascii=False))
        driver.save_screenshot(str(OUT / "a3_ai_source.png"))

        print("\n[7] 最终字段:", json.dumps(js(driver, JS_FIELDS), ensure_ascii=False))
    finally:
        try:
            driver.quit()
        except Exception:
            pass
    print("\n截图目录:", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())

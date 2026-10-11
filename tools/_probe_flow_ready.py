#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针：验证 CDP Chrome + Flow 画布就绪状态。"""
import sys, time
sys.path.insert(0, r'd:\ai_projects\ComfyUI\tools')
from _flow_cdp import resolve_base, attach_flow_page

b = resolve_base()
print('base =', b)
if not b:
    sys.exit(1)
pg = attach_flow_page(b)
time.sleep(4)
print('url      =', pg.eval('location.href'))
print('editor   =', pg.eval("document.querySelectorAll('.ProseMirror').length"))
print('genbtn   =', pg.eval("document.querySelectorAll(\"button[aria-label='Start generation']\").length"))
n = pg.eval("[...document.querySelectorAll(\"img[src*='/asb/'],img[src*='flow-content']\")].length")
print('imgs     =', n)
txt = pg.eval("document.body.innerText.slice(0, 60).replace(/\\n+/g, ' | ')")
print('bodyText =', txt)
pg.close()

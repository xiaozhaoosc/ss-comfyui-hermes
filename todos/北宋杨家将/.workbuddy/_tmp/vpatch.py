# -*- coding: utf-8 -*-
"""把 vspec.py 里的 %d/%s 占位符换成 token，避开正文里的字面百分号。"""
import io, os
P = r"D:\BaiduNetdiskDownload\北宋杨家将\.workbuddy\_tmp\vspec.py"
s = io.open(P, "r", encoding="utf-8").read()

reps = [
 ("<style>%s</style>", "<style>@@CSS@@</style>"),
 ("全片有 <b>%d 个镜头</b>", "全片有 <b>@@RISK@@ 个镜头</b>"),
 ('<div class="v">%d</div><div class="l">Flow 段数（全片）</div>', '<div class="v">@@TOT@@</div><div class="l">Flow 段数（全片）</div>'),
 ('<div class="v">%d</div><div class="l">需重写运镜的镜头</div>', '<div class="v">@@RISK@@</div><div class="l">需重写运镜的镜头</div>'),
 ("4 秒 %d 段 · 6 秒 %d 段 · 8 秒 %d 段", "4 秒 @@D4@@ 段 · 6 秒 @@D6@@ 段 · 8 秒 @@D8@@ 段"),
 ("<td>%d 段（1 镜 = 1 段）</td>", "<td>@@TOT@@ 段（1 镜 = 1 段）</td>"),
 ('<td class="c">%d 张</td><td class="c">5–10</td><td class="c">%s – %s</td>',
  '<td class="c">@@TOT@@ 张</td><td class="c">5–10</td><td class="c">@@IMGLO@@ – @@IMGHI@@</td>'),
 ('<tr><td>视频生成 · Lite</td><td class="c">%d 段</td><td class="c">10</td><td class="c">%s</td></tr>',
  '<tr><td>视频生成 · Lite</td><td class="c">@@TOT@@ 段</td><td class="c">10</td><td class="c">@@VLITE@@</td></tr>'),
 ('<tr><td>视频生成 · Fast</td><td class="c">%d 段</td><td class="c">20</td><td class="c">%s</td></tr>',
  '<tr><td>视频生成 · Fast</td><td class="c">@@TOT@@ 段</td><td class="c">20</td><td class="c">@@VFAST@@</td></tr>'),
 ('<tr><td>视频生成 · Quality</td><td class="c">%d 段</td><td class="c">100</td><td class="c">%s</td></tr>',
  '<tr><td>视频生成 · Quality</td><td class="c">@@TOT@@ 段</td><td class="c">100</td><td class="c">@@VQUAL@@</td></tr>'),
]
n = 0
for a, b in reps:
    if a in s:
        s = s.replace(a, b); n += 1
    else:
        print("MISS: " + a[:50])

# 末尾追加 token 替换
tail = '''
html = "".join(P)
for _k, _v in [("@@CSS@@", CSS), ("@@TOT@@", str(tot)), ("@@RISK@@", str(len(risk))),
               ("@@D4@@", str(cnt[4])), ("@@D6@@", str(cnt[6])), ("@@D8@@", str(cnt[8])),
               ("@@IMGLO@@", format(tot * 5, ",")), ("@@IMGHI@@", format(tot * 10, ",")),
               ("@@VLITE@@", format(tot * 10, ",")), ("@@VFAST@@", format(tot * 20, ",")),
               ("@@VQUAL@@", format(tot * 100, ","))]:
    html = html.replace(_k, _v)
'''
s = s.replace('\nhtml = "".join(P)\n', tail)

io.open(P, "w", encoding="utf-8").write(s)
print("patched=%d" % n)

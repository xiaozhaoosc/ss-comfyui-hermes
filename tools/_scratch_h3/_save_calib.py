# -*- coding: utf-8 -*-
"""把校准结果存到 output/2026-09-21_wb/h3_guard/ 下，作为基线对照。"""
import sys, os, io, json, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import h3_rope_common as H

OUT = H.out_dir("h3_guard")
os.makedirs(OUT, exist_ok=True)

CLIPS = [
    ("sayyes_yolo", r"D:\ai_projects\ComfyUI\output\2026-09-21\shiling_sayyes_h3_yolo_00001-audio.mp4"),
    ("sayyes_c3", r"D:\ai_projects\ComfyUI\output\2026-09-21\shiling_sayyes_h3_c3_00001-audio.mp4"),
    ("sayyes_opt", r"D:\ai_projects\ComfyUI\output\2026-09-21\shiling_sayyes_h3_opt_00001-audio.mp4"),
    ("h3_c3_test", r"D:\ai_projects\ComfyUI\output\2026-09-21\shiling_h3_c3_test_00001-audio.mp4"),
    ("whiskey_c3", r"D:\ai_projects\ComfyUI\output\2026-09-21\shiling_whiskey_h3_c3_00001-audio.mp4"),
]

# 直接复用刚才已经量好的数字（避免重复跑 5 分钟）
rows = [
 {"label":"sayyes_yolo","detect_rate":1.0,"identity":0.9865315939790162,"jitter_ratio":3.935320543443142,"flicker_rate":0.25,"chroma_var":0.29497567120944573,"detail_var":0.2162020131264216,"mar_std":0.025466045700722972,"frame_sharp":264.4861755371094},
 {"label":"sayyes_c3","detect_rate":1.0,"identity":0.9854692287575422,"jitter_ratio":4.008119530546334,"flicker_rate":0.2222222222222222,"chroma_var":0.28558256409282506,"detail_var":0.01715025950912931,"mar_std":0.02213141892445315,"frame_sharp":584.11572265625},
 {"label":"sayyes_opt","detect_rate":1.0,"identity":0.9860699542624782,"jitter_ratio":3.913066258499084,"flicker_rate":0.2361111111111111,"chroma_var":0.29201669400786995,"detail_var":0.21389659089581958,"mar_std":0.025484529932522367,"frame_sharp":264.28375244140625},
 {"label":"h3_c3_test","detect_rate":1.0,"identity":0.9737874872186452,"jitter_ratio":7.3319829700973305,"flicker_rate":0.06944444444444445,"chroma_var":0.2120855808902765,"detail_var":0.03052411441655295,"mar_std":0.026475728109082844,"frame_sharp":981.0406494140625},
 {"label":"whiskey_c3","detect_rate":1.0,"identity":0.9851953642876868,"jitter_ratio":4.15744844146592,"flicker_rate":0.125,"chroma_var":0.18283694768598874,"detail_var":0.07506007656066799,"mar_std":0.03942405514263367,"frame_sharp":844.0393676757812},
]

H.save_json(os.path.join(OUT, "calib_baseline.json"),
            {"generated": time.strftime("%Y-%m-%d %H:%M:%S"),
             "note": "C3 及更早方案的基线量化（用 retinaface det_10g 测得）",
             "rows": rows})

p = H.write_report(os.path.join(OUT, "calib_baseline_report.md"), rows,
                   meta={"度量口径": "insightface RetinaFace(det_10g) 5点关键点 + 112x112对齐像素余弦",
                         "样本": "%d 个已有片段" % len(rows),
                         "结论": "sayyes_yolo = 报告里「还在闪」的基线，chroma_var/detail_var 最差"},
                   title="H3 C3 基线 · 人脸时序稳定性量化")
print("saved:", p)
print("outdir:", OUT)

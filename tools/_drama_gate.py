# -*- coding: utf-8 -*-
"""本地版「路由节点」闸门：进下一步前强制校验前置产物存在，避免在设定/资产不完整时浪费积分跑视频。

对应豆包那套「未通过剧本阶段就无法跳到角色/场景生成」的强制顺序机制。
本脚本只做文件存在性判定（glob），不依赖 ComfyUI 是否在运行，纯本地、零风险。

用法:
  python tools/_drama_gate.py --proj <项目名> --date <YYYY-MM-DD> --stage <assets|video|post>
  python tools/_drama_gate.py --proj mydrama --date 2026-10-10 --stage video

stage 含义:
  assets : 校验 00_concept/script_ep01.json 存在（无设定不出图）
  video  : 校验 剧本 + 角色资产图 + 分镜 JSON 都在（进视频前）
  post   : 校验 03_video/ 下至少有 1 个 mp4（进后期前）

退出码 0=通过, 1=未通过（可被批处理 / CI 用来卡流程）。
"""
import argparse
import glob
import os
import sys

ROOT = r"D:\ai_projects\ComfyUI"


def _p(date, proj, rel):
    return os.path.join(ROOT, "output", date, proj, rel)


def _checks(date, proj, stage):
    if stage == "assets":
        return {
            "剧本 script_ep01.json": _p(date, proj, "00_concept/script_ep01.json"),
        }
    if stage == "video":
        return {
            "剧本 script_ep01.json": _p(date, proj, "00_concept/script_ep01.json"),
            "角色资产图 char_*_sheet.png": _p(date, proj, "01_assets/char_*_sheet.png"),
            "分镜 storyboard.json": _p(date, proj, "02_storyboard/storyboard.json"),
        }
    if stage == "post":
        return {
            "视频产物 03_video/*.mp4": _p(date, proj, "03_video/*.mp4"),
        }
    return {}


def main():
    ap = argparse.ArgumentParser(description="AI 动漫短剧 · 本地路由闸门")
    ap.add_argument("--proj", required=True, help="项目名（对应 output/<date>/<proj>）")
    ap.add_argument("--date", required=True, help="日期 YYYY-MM-DD")
    ap.add_argument("--stage", required=True, choices=["assets", "video", "post"])
    a = ap.parse_args()

    checks = _checks(a.date, a.proj, a.stage)
    ok = True
    print(f"[gate:{a.stage}] proj={a.proj} date={a.date}")
    for name, pat in checks.items():
        present = bool(glob.glob(pat))
        ok = ok and present
        print(f"  [{'PASS' if present else 'FAIL'}] {name}\n        ({pat})")
    print("RESULT:", "PASS  可进入下一步" if ok else "BLOCK  前置未满足，先补齐再继续")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

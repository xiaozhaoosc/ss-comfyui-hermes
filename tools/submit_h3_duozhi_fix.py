#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多肢修复版（Aiden 法线参考工作流 + ControlNet 开启 + SelfLift 调参）提交器。

一次性脚本的持久化版本： work-flows/v6/1-Aiden-动作迁移升级版本！法线参考！！_多肢修复版.json
是 UI 格式，这里做 UI→API 转换 + bypass 重路 + 三项入参覆盖后提交。

用法:
  python tools/submit_h3_duozhi_fix.py --ref 8 --driver peach --prefix v6_fix_8
  python tools/submit_h3_duozhi_fix.py --all
"""
import argparse
import collections
import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8188"
# os.environ 里的代理会劫持 127.0.0.1:8188，必须显式绕开
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

SRC = (r"D:\ai_projects\ComfyUI\workflows\v6"
       r"\1-Aiden-动作迁移升级版本！法线参考！！_多肢修复版.json")

REFS = {
    "5": r"ken4/face/小G3/Gemini_Generated_Image_ (5).jpg",
    "8": r"ken4/face/小G3/Gemini_Generated_Image_ (8).jpg",
}
DRIVERS = {
    "peach": r"todo/邪恶de水蜜桃/15030796049432976072_xWT158_576x1024.mp4",
    "baimo": r"白模1.mp4",
    "wm_202610": r"wm_202610.mp4",
}

WIDGET_TYPES = frozenset((
    "INT", "FLOAT", "STRING", "BOOLEAN", "COMBO", "IMAGEUPLOAD", "DTYPE",
))
# 动态下拉：占 1 格存 key，后面紧跟所选 key 的子输入（如 selection=sol-attn → selection.tau）
DYNAMIC_COMBO = "COMFY_DYNAMICCOMBO_V3"
AUTOGROW = "COMFY_AUTOGROW_V3"


def frames_for(seconds):
    """复刻 #42 的帧数公式：max(5, round(a*24)) + (5 - (max % 17)) % 17。

    #41 PrimitiveFloat 存的是"目标秒数"，#42 同时喂 #12.length、#117.frame_load_cap
    和 #13.preview_frames；#163 EmptyImage 的 batch_size 必须跟它一致，否则白模支路
    会被压成 1 帧（comfy 的 composite 返回 destination，批长跟 destination 走）。
    """
    n = max(5, round(float(seconds) * 24))
    return n + (5 - (n % 17)) % 17


def sync_length(prompt, seconds=None):
    """把 #41 目标秒数、#163 batch_size 对齐到同一个帧数。"""
    if seconds is not None:
        prompt["41"]["inputs"]["value"] = seconds
    secs = prompt["41"]["inputs"]["value"]
    prompt["163"]["inputs"]["batch_size"] = frames_for(secs)
    return prompt


def get_json(path, timeout=180):
    with OPENER.open(urllib.request.Request(BASE + path), timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def use_gpu_encode(prompt):
    """把 VHS_VideoCombine 的输出编码从 libx264 软编换成 h264_nvenc（GPU）。

    工作流原本是 video/h264-mp4（libx264，全程 CPU）；4060Ti 支持 NVENC，
    VHS 自带 nvenc_h264-mp4 格式。切格式后 h264 专有的 crf/trim_to_audio
    要换成 nvenc 的 bitrate/megabit，否则服务端会报 required_input_missing。
    """
    for nid in ("111", "112", "115"):
        node = prompt.get(nid)
        if not node:
            continue
        ins = node["inputs"]
        if not str(ins.get("format", "")).startswith("video/"):
            continue
        ins["format"] = "video/nvenc_h264-mp4"
        for k in ("crf", "trim_to_audio"):
            ins.pop(k, None)
        ins["pix_fmt"] = "yuv420p"
        ins.setdefault("bitrate", 10)
        ins.setdefault("megabit", True)


def build():
    wf = json.load(open(SRC, encoding="utf-8"))
    nodes = {n["id"]: n for n in wf["nodes"]}
    links = {l[0]: l for l in wf["links"]}

    # 结构自检
    ids = [n["id"] for n in wf["nodes"]]
    assert len(ids) == len(set(ids)), "节点 id 重复"
    bad = [l for l in wf["links"] if l[1] not in nodes or l[3] not in nodes]
    assert not bad, f"悬空连线 {bad[:5]}"

    oi = get_json("/object_info")

    def widget_specs(t):
        """返回按 widgets_values 顺序排列的槽位描述符。

        坑（全部实测）：
          1. 带 control_after_generate 的 INT（如 seed）会额外占一格存随机策略字符串；
          2. 被连接的 widget 依然保留它在 widgets_values 里的槽位，不能直接跳过，
             否则后面所有参数整体错位（实测 #13 tiny_vae 吃到 preview_fps 的值）；
          3. forceInput 的输入永远是插槽、AUTOGROW 是占位，都不占槽位；
          4. 新版下拉写成 ["COMBO", {...}]，类型名是字符串而不是选项数组，必须认；
          5. DYNAMICCOMBO 占 1 格存 key，并紧跟所选 key 的子输入（selection.tau）。
        """
        info = oi.get(t)
        if not info:
            return []
        d = info.get("input") or {}
        order = info.get("input_order") or {}
        specs = []
        for sect in ("required", "optional"):
            names = order.get(sect) or list((d.get(sect) or {}).keys())
            for k in names:
                v = (d.get(sect) or {}).get(k)
                if not isinstance(v, list) or not v:
                    continue
                t0 = v[0]
                opts = v[1] if len(v) > 1 and isinstance(v[1], dict) else {}
                if opts.get("forceInput") or t0 == AUTOGROW:
                    continue
                if t0 == DYNAMIC_COMBO:
                    specs.append({"kind": "dyn", "name": k, "opts": opts})
                elif isinstance(t0, list) or t0 in WIDGET_TYPES:
                    specs.append({"kind": "w", "name": k,
                                  "extra": 1 if opts.get("control_after_generate") else 0})
        return specs

    def dyn_sub_inputs(opts, key):
        """动态下拉选中某个 key 时，它带来的子输入名（按顺序）。"""
        for opt in (opts.get("options") or []):
            if opt.get("key") == key:
                tmpl = opt.get("inputs") or {}
                # 选项模板有的包一层 "input"，有的直接就是 {"required": {...}}
                torder = tmpl.get("input_order") or {}
                td = tmpl.get("input") or tmpl
                names = []
                for sect in ("required", "optional"):
                    for sk in (torder.get(sect) or list((td.get(sect) or {}).keys())):
                        names.append((
                            sk,
                            1 if isinstance(td[sect][sk][1], dict)
                            and td[sect][sk][1].get("control_after_generate") else 0,
                        ))
                return names
        return []

    # bypass (mode 4) 重路：输出直接接回同类型的输入
    for b in [n for n in nodes.values() if n.get("mode", 0) == 4]:
        bins = [i for i in b.get("inputs", []) if i.get("link") is not None]
        for out in b.get("outputs") or []:
            for lid in (out.get("links") or []):
                pick = next((i for i in bins if i.get("type") == out.get("type")), None)
                if pick is None and len(bins) == 1:
                    pick = bins[0]
                if pick and pick["link"] in links:
                    s = links[pick["link"]]
                    links[lid] = [lid, s[1], s[2], links[lid][3], links[lid][4], links[lid][5]]

    def put(dst, key, val):
        # autogrow 输入必须保留扁平点号键（ref_images.ref_image_0 / values.a），
        # 拆成嵌套 dict 会被服务端判定 required_input_missing
        dst[key] = val

    prompt = {}
    unknown = collections.Counter()
    for nid, n in nodes.items():
        if n.get("mode", 0) != 0 or n["type"] in ("Note", "MarkdownNote"):
            continue
        t = n["type"]
        if t not in oi:
            unknown[t] += 1
        entry = {"class_type": t, "inputs": {}}
        for inp in n.get("inputs") or []:
            lid = inp.get("link")
            if lid is not None and lid in links:
                l = links[lid]
                put(entry["inputs"], inp["name"], [str(l[1]), l[2]])
        wv = n.get("widgets_values")
        specs = widget_specs(t)
        if wv is not None and specs:
            if isinstance(wv, dict):
                # 坑：dict 格式（VHS_VideoCombine / VHS_LoadVideo）同样可能某个 widget
                # 已转成连接输入，此时字典里的旧值必须让位给 [node, slot]，
                # 否则 frame_load_cap 会被写死成旧数字、不再跟着 #42 算。
                linked = set(entry["inputs"].keys())
                for s in specs:
                    if s["name"] in linked:
                        continue
                    if s["name"] in wv:
                        entry["inputs"][s["name"]] = wv[s["name"]]
            else:
                linked = set(entry["inputs"].keys())
                i = 0
                for s in specs:
                    if i >= len(wv):
                        break
                    name = s["name"]
                    if s["kind"] == "w":
                        if name not in linked:
                            entry["inputs"][name] = wv[i]
                        i += 1 + s["extra"]
                    else:  # 动态下拉：先 key，再它带来的子输入
                        key = wv[i]
                        i += 1
                        if name not in linked:
                            entry["inputs"][name] = key
                        for sub, extra in dyn_sub_inputs(s["opts"], key):
                            if i >= len(wv):
                                break
                            entry["inputs"]["%s.%s" % (name, sub)] = wv[i]
                            i += 1 + extra
        prompt[str(nid)] = entry
    sync_length(prompt)
    use_gpu_encode(prompt)
    return prompt, nodes, unknown


def submit(prompt, nodes, client_id="v6-duozhi-fix"):
    body = json.dumps({"prompt": prompt, "client_id": client_id}).encode("utf-8")
    req = urllib.request.Request(BASE + "/prompt", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with OPENER.open(req, timeout=300) as r:
            res = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print("[提交失败] HTTP", e.code)
        try:
            err = json.loads(e.read().decode("utf-8"))
            print("error:", json.dumps(err.get("error", {}), ensure_ascii=False)[:1500])
            for k, v in (err.get("node_errors") or {}).items():
                print("  节点 %s (%s):" % (k, nodes.get(int(k), {}).get("type")))
                for e2 in v.get("errors", []):
                    print("    - %s: %s | %s" % (e2.get("type"), e2.get("message"),
                                                 str(e2.get("details"))[:300]))
        except Exception as ex:
            print("raw:", ex)
        return None
    if res.get("node_errors"):
        print("[node_errors]", json.dumps(res["node_errors"], ensure_ascii=False)[:2000])
        return None
    return res


VARIANTS = {
    # base: Aiden 原参（cn .45 / end .75 / normal_opengl）
    "base": {},
    # mode: 换 MoGeRender 输出模式，验证网格是不是它的渲染风格带出来的
    "mode": {"moge_output": "normal_directx"},
    # soft: 降 ControlNet 强度/作用区间，让它只锁前半段骨架、不复制纹理
    "soft": {"cn_strength": 0.2, "cn_end": 0.4},
    # blur: 只对喂 ControlNet 的支路做轻度模糊（#92 → blur → #126），ref_video 不动
    "blur": {"cn_blur": 3, "cn_blur_sigma": 3.0},
    # strong: 加强运动约束 —— 治「手臂/腿部动作没迁移」
    #   ControlNet 强度 0.45→0.8、作用区间 0→100%、SelfLift 提前(第4步)切高清，
    #   避免 8 步采样里 cn 只在前 ~2 步有效就被 SelfLift 的高清跃迁覆盖。
    "strong": {"cn_strength": 0.8, "cn_end": 1.0, "transition_step": 4},
}


def apply_variant(prompt, variant):
    """按 variant 改图；返回 (prompt, 说明)。"""
    cfg = VARIANTS.get(variant)
    if cfg is None:
        raise SystemExit("未知 variant %r，可选: %s" % (variant, list(VARIANTS)))
    notes = []
    if "moge_output" in cfg:
        prompt["67"]["inputs"]["output"] = cfg["moge_output"]
        notes.append("MoGeRender.output=%s" % cfg["moge_output"])
    if "cn_strength" in cfg:
        prompt["126"]["inputs"]["strength"] = cfg["cn_strength"]
        notes.append("cn_strength=%s" % cfg["cn_strength"])
    if "cn_end" in cfg:
        prompt["126"]["inputs"]["end_percent"] = cfg["cn_end"]
        notes.append("cn_end_percent=%s" % cfg["cn_end"])
    if "transition_step" in cfg:
        prompt["20"]["inputs"]["transition_step"] = cfg["transition_step"]
        notes.append("SelfLift transition_step=%s" % cfg["transition_step"])
    if "cn_blur" in cfg:
        # 新节点只插在 ControlNet 分支上：#12.ref_videos.ref_video_0 仍吃原图
        prompt["900"] = {"class_type": "ImageBlur",
                         "inputs": {"image": ["92", 0],
                                    "blur_radius": cfg["cn_blur"],
                                    "sigma": cfg["cn_blur_sigma"]}}
        prompt["126"]["inputs"]["control_video"] = ["900", 0]
        notes.append("cn 前置 ImageBlur r=%s sigma=%s" % (cfg["cn_blur"], cfg["cn_blur_sigma"]))
    return prompt, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", choices=list(REFS), default="8")
    ap.add_argument("--driver", choices=list(DRIVERS), default="peach")
    ap.add_argument("--prefix", default=None)
    ap.add_argument("--all", action="store_true", help="5/8 两张参考图各一条")
    ap.add_argument("--variant", choices=list(VARIANTS), default="base")
    ap.add_argument("--seconds", type=float, default=None,
                    help="目标秒数（写 #41 PrimitiveFloat；默认沿用工作流的 5s）")
    ap.add_argument("--keep-batch1", action="store_true",
                    help="保留 #163 batch_size=1 的坏行为（复现白模塌成 1 帧，仅用于对照）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    jobs = [(r, args.driver) for r in ("5", "8")] if args.all else [(args.ref, args.driver)]

    for ref_key, drv in jobs:
        prompt, nodes, unknown = build()
        # 关键覆盖：参考图 / 驱动视频 / 输出前缀
        prompt["29"]["inputs"]["image"] = REFS[ref_key]
        prompt["117"]["inputs"]["video"] = DRIVERS[drv]
        prefix = args.prefix or ("v6_%s_%s" % (args.variant, ref_key))
        prompt["115"]["inputs"]["filename_prefix"] = prefix
        prompt, notes = apply_variant(prompt, args.variant)
        if args.keep_batch1:
            prompt["163"]["inputs"]["batch_size"] = 1
            notes.append("batch_size 保持 1（坏行为对照）")
        else:
            # #163 EmptyImage.batch_size 必须等于帧数，否则白模支路塌成 1 帧
            prompt = sync_length(prompt, args.seconds)
            notes.append("#163 batch_size=%d (#41=%ss)" % (
                prompt["163"]["inputs"]["batch_size"], prompt["41"]["inputs"]["value"]))

        print("== ref=%s driver=%s variant=%s prefix=%s ==" % (ref_key, drv, args.variant, prefix))
        print("   #29 %s=%s" % (nodes[29]["type"], prompt["29"]["inputs"]["image"]))
        print("   #117 video=%s" % prompt["117"]["inputs"]["video"])
        print("   #67 MoGeRender.output=%s" % prompt["67"]["inputs"]["output"])
        print("   #126 cn strength=%s start=%s end=%s control_video=%s"
              % (prompt["126"]["inputs"]["strength"], prompt["126"]["inputs"]["start_percent"],
                 prompt["126"]["inputs"]["end_percent"], prompt["126"]["inputs"]["control_video"]))
        print("   #20 SelfLift cfg=%s rho=%s w_min=%s transition_step=%s" % (
            prompt["20"]["inputs"].get("cfg"), prompt["20"]["inputs"].get("rho"),
            prompt["20"]["inputs"].get("w_min"), prompt["20"]["inputs"].get("transition_step")))
        print("   改动: %s" % ("; ".join(notes) or "(none)"))
        n12 = prompt["12"]["inputs"]
        print("   #12 length=%s size=%sx%s | #117 cap=%s | #41=%s | #42=%s"
              % (n12.get("length"), n12.get("width"), n12.get("height"),
                 prompt["117"]["inputs"].get("frame_load_cap"),
                 prompt["41"]["inputs"].get("value"),
                 prompt["42"]["inputs"].get("expression")))
        print("   节点数=%d 未注册=%s" % (len(prompt), dict(unknown) or "(无)"))
        if args.dry_run:
            continue
        res = submit(prompt, nodes)
        if res:
            print("   >>> prompt_id=%s number=%s" % (res.get("prompt_id"), res.get("number")))
    return 0


if __name__ == "__main__":
    sys.exit(main())

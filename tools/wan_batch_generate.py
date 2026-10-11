"""
WanAnimate 多分块动作迁移 · 批量生成器（按驱动视频帧数自动分块）

基于 workflows/v3/motion_transfer_wan_animate_multichunk_full_api.json，修正了源码级复核发现的问题：
  P0-1 ImageScale 512x512 crop=center 会把竖屏驱动视频中心裁掉 ~44% 人体 → 改为保持 9:16 比例
  P0-2 GetImageRangeFromBatch 的 start_index 恒为 0 → 改为接上一块的 trim_image（=5），
      且偏移用节点真实的 video_frame_offset 递推（0,49,93,137…）替代硬编码 0/45/89/133
  P0-3 UI 版 continue_motion 未连线 → 本脚本生成���连线版

用法：
  python tools/wan_batch_generate.py --list
  python tools/wan_batch_generate.py --ref "1todos/清透冷调红唇肖像.png" --dry-run
  python tools/wan_batch_generate.py --ref "1todos/清透冷调红唇肖像.png" --only 3
  python tools/wan_batch_generate.py --ref "1todos/清透冷调红唇肖像.png" --start 0 --end 2
"""
import argparse, json, os, subprocess, sys, time, urllib.request, urllib.error, uuid

ROOT = r"d:\ai_projects\ComfyUI"
WF = os.path.join(ROOT, "workflows", "v3", "motion_transfer_wan_animate_multichunk_full_api.json")
VIDEO_DIR_REL = "Ms.琪大宝er"
OUT_PREFIX = "2026-10-10_wb/wan_batch_qingdao"
SERVER = "http://127.0.0.1:8188"

LENGTH = 49          # 每块生成帧数（必须是 1+4k）
CMF = 5              # continue_motion_max_frames
TRIM = ((CMF - 1) // 4 + 1) * 4 - 3   # =5，衔接区帧数（节点 trim_image 公式）
SEED0 = 20261000

# 简易方案：提示词固定服装（WanAnimateToVideo 无服装输入，只能靠提示词）
DEFAULT_CLOTHES = ("wearing a black sleeveless halter top and gray drawstring sweatpants, "
                   "full body visible from head to toe")
DEFAULT_POS = ("A photorealistic cinematic full-body video of the character, naturally performing "
               "the motion from reference video, natural facial expressions, gentle blinking, "
               "relaxed hands, sharp focus, 8k uhd, masterpiece")
DEFAULT_NEG = ("bad quality, blurry, deformed limbs, extra fingers, missing limbs, bad anatomy, "
               "mutated hands, multiple arms, three arms, glitch, face distortion, flickering, "
               "cropped head, cropped feet, out of frame")


def opener():
    """本机设了 HTTP_PROXY，必须绕代理，否则 127.0.0.1:8188 返回 502"""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def ensure_in_input(rel, subdir="1todos/ref_build"):
    """LoadImage 只能读 input/；若给的是 output/ 相对路径或绝对路径，自动复制进 input 并返回相对路径。"""
    import shutil
    p = rel.replace("\\", "/")
    if os.path.exists(os.path.join(ROOT, "input", p)):
        return p
    src = p if os.path.isabs(p) else None
    if src is None:
        for b in (ROOT, os.path.join(ROOT, "output")):
            c = os.path.join(b, p)
            if os.path.exists(c):
                src = c
                break
    if src is None or not os.path.exists(src):
        raise FileNotFoundError(f"找不到参考图: {rel}")
    dst_dir = os.path.join(ROOT, "input", subdir)
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(src))
    shutil.copy2(src, dst)
    return f"{subdir}/{os.path.basename(src)}"


def probe(path):
    """ffprobe -> (w,h,fps,frames)"""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,width,height,r_frame_rate,nb_frames",
         "-of", "json", path],
        capture_output=True, text=True, timeout=60).stdout
    j = json.loads(out)
    v = [s for s in j["streams"] if s["codec_type"] == "video"][0]
    num, den = v["r_frame_rate"].split("/")
    fps = int(num) / int(den) if int(den) else 30.0
    nf = int(v.get("nb_frames") or 0)
    if not nf:  # 某些 mp4 缺 nb_frames
        nf = int(subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
             "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=180).stdout.strip() or 0)
    return v["width"], v["height"], fps, nf


def plan_chunks(total_frames, length=LENGTH, cmf=CMF):
    """
    按节点源码递推 video_frame_offset：
        首块（无 continue_motion）：out = in + length
        后续块（有 continue_motion）：out = (in - cmf) + length
    返回 [(offset, keep_frames), ...]；keep = 该块裁切后应保留的帧数
      首块保留 length；后续块要裁掉开头 TRIM 帧衔接区，故保留 length-TRIM
    """
    chunks, off = [], 0
    while len(chunks) < 40:
        chunks.append(off)
        off = (off + length) if len(chunks) == 1 else (off - cmf) + length
        if off >= total_frames:
            break
    out = []
    for i, o in enumerate(chunks):
        keep = length if i == 0 else length - TRIM
        remain = total_frames - o          # 源视频剩余帧数
        if remain <= 0:
            break
        if remain < keep:                  # 末块截断，避免生成空白
            keep = remain
        out.append((o, keep))
    return out


def build_graph(ref_path, video_rel, chunks, save_name, clothes=None, pos=None, neg=None):
    with open(WF, "r", encoding="utf-8") as f:
        base = json.load(f)

    # 保留 1–13 及两个 DWPreprocessor(15/16)；14 会被下面的 9:16 版本覆盖
    g = {k: json.loads(json.dumps(v)) for k, v in base.items()
         if k in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "15", "16")}
    g["10"]["inputs"]["image"] = ref_path
    g["12"]["inputs"]["file"] = video_rel
    # 简易方案：服装/构图写进提示词
    g["8"]["inputs"]["text"] = (pos or DEFAULT_POS) + ", " + (clothes or DEFAULT_CLOTHES)
    g["9"]["inputs"]["text"] = neg or DEFAULT_NEG

    # P0-1：保持 9:16，不再中心裁切成方形（否则 DWPose 拿不到全身）
    # 注意：ImageScale.crop 只接受 disabled / center；disabled = 不裁剪(拉伸)，正是我们要的
    g["14"] = {"class_type": "ImageScale", "_meta": {"title": "驱动帧缩放 288x512 (保持9:16, 供骨骼提取)"},
               "inputs": {"image": ["13", 0], "upscale_method": "lanczos",
                          "width": 288, "height": 512, "crop": "disabled"}}

    # P0-2：用真实 offset 递推 + start_index=trim_image 裁掉衔接区
    prev_vae = None
    for i, (off, keep) in enumerate(chunks):
        wan, ks, vae = f"{100+i}1", f"{100+i}2", f"{100+i}3"
        tri = f"{100+i}4"
        gin = {
            "positive": ["8", 0], "negative": ["9", 0], "vae": ["3", 0],
            "width": 480, "height": 832, "length": LENGTH, "batch_size": 1,
            "continue_motion_max_frames": CMF, "video_frame_offset": off,
            "clip_vision_output": ["11", 0], "reference_image": ["10", 0],
            "face_video": ["15", 0], "pose_video": ["16", 0],
        }
        if prev_vae:
            gin["continue_motion"] = [prev_vae, 0]
        g[wan] = {"class_type": "WanAnimateToVideo",
                  "_meta": {"title": f"Chunk {i+1} (Offset={off})"}, "inputs": gin}
        g[ks] = {"class_type": "KSampler", "_meta": {"title": f"KSampler Chunk {i+1}"},
                 "inputs": {"model": ["7", 0], "seed": SEED0 + 10 * i + 9, "steps": 4, "cfg": 1.0,
                            "sampler_name": "euler", "scheduler": "simple",
                            "positive": [wan, 0], "negative": [wan, 1],
                            "latent_image": [wan, 2], "denoise": 1.0}}
        g[vae] = {"class_type": "VAEDecode", "_meta": {"title": f"VAEDecode Chunk {i+1}"},
                  "inputs": {"samples": [ks, 0], "vae": ["3", 0]}}
        g[tri] = {"class_type": "GetImageRangeFromBatch", "_meta": {"title": f"Trim Chunk {i+1} -> {keep}f"},
                  "inputs": {"images": [vae, 0],
                             "start_index": 0 if i == 0 else TRIM,
                             "num_frames": keep}}
        prev_vae = vae

    # 逐级 ImageBatch 缝合
    # ⚠️ 节点 ID 基址必须远离 710(CreateVideo)/720(SaveVideo)：曾用 700+i，
    #    当分块数=11 时 700+10=710 会覆盖 CreateVideo → 报 images received_type(VIDEO) mismatch
    prev = f"{100}4"
    for i in range(1, len(chunks)):
        nid = str(8000 + i)
        g[nid] = {"class_type": "ImageBatch", "_meta": {"title": f"合并 chunk{i} + chunk{i+1}"},
                  "inputs": {"image1": [prev, 0], "image2": [f"{100+i}4", 0]}}
        prev = nid
    total = sum(c[1] for c in chunks)

    g["710"] = {"class_type": "CreateVideo", "_meta": {"title": f"合成 {total} 帧 (原fps+原音频)"},
                "inputs": {"images": [prev, 0], "fps": ["13", 2], "audio": ["13", 1]}}
    g["720"] = {"class_type": "SaveVideo", "_meta": {"title": "保存"},
                "inputs": {"video": ["710", 0], "filename_prefix": save_name,
                           "format": "auto", "codec": "auto"}}
    return g, total


def post_json(path, obj, timeout=120):
    req = urllib.request.Request(SERVER + path,
                                 data=json.dumps(obj).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    return json.loads(opener().open(req, timeout=timeout).read().decode())


def get_json(path, timeout=60):
    return json.loads(opener().open(SERVER + path, timeout=timeout).read().decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="1todos/清透冷调红唇肖像.png")
    ap.add_argument("--videos", default=VIDEO_DIR_REL)
    ap.add_argument("--only", type=int, default=None, help="只跑第 N 个（0-based）")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--clothes", default=None, help="服装描述（简易方案：写进提示词）")
    ap.add_argument("--pos", default=None, help="自定义正向提示词")
    ap.add_argument("--neg", default=None, help="自定义负向提示词")
    ap.add_argument("--prefix", default=OUT_PREFIX, help="输出前缀")
    ap.add_argument("--no-wait", action="store_true",
                    help="只提交不等待（任务留在 ComfyUI 服务端队列，客户端可退出）")
    a = ap.parse_args()
    submitted = []

    vdir = os.path.join(ROOT, "input", a.videos)
    vids = sorted(f for f in os.listdir(vdir) if f.lower().endswith((".mp4", ".mov", ".webm")))
    if a.list:
        for i, v in enumerate(vids):
            print(f"{i:2d}  {v}")
        return

    # 参考图可能来自 output/（如上游 ReActor 产物）→ 自动复制进 input
    ref_rel = ensure_in_input(a.ref) if not a.dry_run else a.ref
    print("reference:", ref_rel)

    q = get_json("/queue")
    if q.get("queue_running"):
        print("[WARN] ComfyUI 当前有任务在跑，将排队等待。")

    idxs = list(range(len(vids)))
    if a.only is not None:
        idxs = [a.only]
    elif a.start or (a.end is not None):
        idxs = idxs[a.start: (a.end if a.end is not None else len(idxs))]

    for n, i in enumerate(idxs):
        vname = vids[i]
        vpath = os.path.join(vdir, vname)
        w, h, fps, nf = probe(vpath)
        chunks = plan_chunks(nf)
        total = sum(c[1] for c in chunks)
        rel = f"{a.videos}/{vname}"
        safe = "".join("_" if ch in '#/\\:*?"<>|' else ch for ch in os.path.splitext(vname)[0])[:28]
        save = f"{a.prefix}_{i:02d}_{safe}"

        print(f"\n[{n+1}/{len(idxs)}] {vname}")
        print(f"   源: {w}x{h} {fps:.2f}fps {nf}帧 ({nf/fps:.2f}s) -> {len(chunks)}块, 输出{total}帧 ({total/fps:.2f}s)")
        print(f"   偏移: {[c[0] for c in chunks]}")
        if a.dry_run:
            continue

        graph, total = build_graph(ref_rel, rel, chunks, save, a.clothes, a.pos, a.neg)
        try:
            r = post_json("/prompt", {"prompt": graph, "client_id": str(uuid.uuid4())})
        except urllib.error.HTTPError as e:
            # 必须读body：ComfyUI 的校验错误（如缺节点/非法枚举值）都在这里
            body = e.read().decode("utf-8", "replace")
            try:
                errs = json.loads(body).get("node_errors", {})
                msgs, seen = [], set()
                for nid, info in errs.items():
                    for er in info.get("errors", []):
                        d = str(er.get("details") or er.get("message"))[:160]
                        key = (info.get("class_type"), d)
                        if key not in seen:
                            seen.add(key)
                            msgs.append(f"node {nid} {info.get('class_type')}: {d}")
                print("   [FAIL] 提交被拒:", "; ".join(msgs[:4]))
            except Exception:
                print("   [FAIL] HTTP", e.code, body[:300])
            continue
        except Exception as e:
            print("   [FAIL] 提交失败:", e)
            continue
        pid = r["prompt_id"]
        submitted.append((vname, pid, len(chunks), total))
        if a.no_wait:
            print(f"   已提交 prompt_id={pid} （no-wait，不等待）")
            continue
        print(f"   已提交 prompt_id={pid} 等待渲染…")
        t0 = time.time()
        done = False
        while time.time() - t0 < 7200:
            try:
                h = get_json(f"/history/{pid}")
            except Exception:
                time.sleep(5); continue
            if pid in h:
                st = h[pid].get("status", {})
                if st.get("completed") or st.get("status_str") == "success":
                    outs = h[pid].get("outputs", {})
                    vid = outs.get("720", {})
                    print(f"   [OK] {time.time()-t0:.0f}s -> {vid}")
                    done = True
                else:
                    print("   [FAIL]", str(st.get("messages"))[:300])
                break
            time.sleep(5)
        if not done and time.time() - t0 >= 7200:
            print("   [TIMEOUT]")

    # 出片收尾：生成扁平画廊，一屏验收全部产物（失败不影响主流程）
    if a.no_wait and submitted:
        print("\n===== 已全部提交到 ComfyUI 服务端队列（客户端可退出）=====")
        for vn, pid, nc, tf in submitted:
            print(f"  {pid}  {nc}块 {tf}帧  {vn}")
        man = os.path.join(ROOT, "output", os.path.dirname(a.prefix),
                           f"_batch_{os.path.basename(a.prefix)}_submitted.txt")
        os.makedirs(os.path.dirname(man), exist_ok=True)
        with open(man, "w", encoding="utf-8") as f:
            for vn, pid, nc, tf in submitted:
                f.write(f"{pid}\t{nc}\t{tf}\t{vn}\n")
        print("清单:", man)
    elif not a.dry_run:
        out_dir = os.path.join(ROOT, "output", os.path.dirname(a.prefix))
        try:
            if ROOT not in sys.path:
                sys.path.insert(0, ROOT)
            from tools.flat_gallery import generate_gallery
            generate_gallery(out_dir, quiet=True)
        except Exception as e:
            print(f"[!] 画廊生成跳过: {e}")


if __name__ == "__main__":
    main()
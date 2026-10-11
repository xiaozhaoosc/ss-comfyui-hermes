"""
Stage 3: 对 WanAnimate 成片逐帧做 ReActor 脸部锁定 + 原音频/帧率还原

链路：LoadVideo -> GetVideoComponents -> ReActorFaceSwapOpt(per-frame) -> CreateVideo -> SaveVideo
注意：ReActor 是整批 IMAGE 张量一起处理（不是逐帧 loop），GetVideoComponents 出来的 images
      本身就是一个 batch，直接喂进去即可。

用法：
  python tools/wan_stage3_facelock_video.py \
      --video "2026-10-10_wb/wan_locked01_01__会有人喜欢嘛_00001_.mp4" \
      --source "1todos/005-822807425_18090503405430819_9034340549182780041_n.jpeg"
"""
import argparse, json, os, shutil, time, urllib.request, urllib.error, uuid

ROOT = r"d:\ai_projects\ComfyUI"
SERVER = "http://127.0.0.1:8188"
DEFAULT_SOURCE = "1todos/005-822807425_18090503405430819_9034340549182780041_n.jpeg"


def opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def ensure_in_input(rel):
    """LoadVideo/LoadImage 只能读 input/；把 output 产物复制进来。"""
    p = rel.replace("\\", "/")
    if os.path.exists(os.path.join(ROOT, "input", p)):
        return p
    bases = [ROOT, os.path.join(ROOT, "output")]
    src = p if os.path.isabs(p) else None
    if src is None:
        for b in bases:
            c = os.path.join(b, p)
            if os.path.exists(c):
                src = c
                break
    if src is None or not os.path.exists(src):
        raise FileNotFoundError(f"找不到: {rel}")
    dst_dir = os.path.join(ROOT, "input", "1todos", "facelock")
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(src))
    shutil.copy2(src, dst)
    return "1todos/facelock/" + os.path.basename(src)


def build(video_rel, source_rel, restore="GFPGANv1.4.pth", visibility=1.0,
          prefix=None, detect="retinaface_resnet50"):
    g = {}
    g["1"] = {"class_type": "LoadVideo", "inputs": {"file": video_rel}}
    g["2"] = {"class_type": "GetVideoComponents", "inputs": {"video": ["1", 0]}}
    g["3"] = {"class_type": "LoadImage", "inputs": {"image": source_rel}}
    g["4"] = {"class_type": "ReActorFaceSwapOpt", "_meta": {"title": "ReActor 锁脸 (per-frame)"},
              "inputs": {"enabled": True,
                         "input_image": ["2", 0],
                         "source_image": ["3", 0],
                         "swap_model": "inswapper_128.onnx",
                         "facedetection": detect,
                         "face_restore_model": restore,
                         "face_restore_visibility": visibility,
                         "codeformer_weight": 0.5}}
    g["5"] = {"class_type": "CreateVideo",
              "inputs": {"images": ["4", 0], "fps": ["2", 2], "audio": ["2", 1]}}
    g["6"] = {"class_type": "SaveVideo",
              "inputs": {"video": ["5", 0],
                         "filename_prefix": prefix or "2026-10-10_wb/wan_facelock/out",
                         "format": "auto", "codec": "auto"}}
    return g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--source", default=DEFAULT_SOURCE)
    ap.add_argument("--restore", default="GFPGANv1.4.pth", choices=["none", "GFPGANv1.4.pth", "codeformer.pth"])
    ap.add_argument("--visibility", type=float, default=1.0)
    ap.add_argument("--detect", default="retinaface_resnet50",
                    choices=["retinaface_resnet50", "retinaface_mobile0.25", "YOLOv5l", "YOLOv5n"])
    ap.add_argument("--prefix", default=None)
    a = ap.parse_args()

    vid = ensure_in_input(a.video)
    src = ensure_in_input(a.source)
    print("video :", vid)
    print("source:", src)
    g = build(vid, src, a.restore, a.visibility, a.prefix, a.detect)
    req = urllib.request.Request(SERVER + "/prompt",
                                 data=json.dumps({"prompt": g, "client_id": str(uuid.uuid4())}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        r = json.loads(opener().open(req, timeout=120).read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            errs = json.loads(body).get("node_errors", {})
            for nid, info in errs.items():
                for er in info.get("errors", []):
                    print("REJECTED node", nid, info.get("class_type"), ":", str(er.get("details"))[:220])
        except Exception:
            print("REJECTED:", body[:700])
        return
    pid = r["prompt_id"]
    print("submitted", pid, "-> waiting…")
    t0 = time.time()
    while time.time() - t0 < 3600:
        try:
            h = json.loads(opener().open(f"{SERVER}/history/{pid}", timeout=20).read().decode())
        except Exception:
            time.sleep(5); continue
        if pid in h:
            st = h[pid].get("status", {})
            for v in h[pid].get("outputs", {}).values():
                for k in ("videos", "gifs", "images"):
                    for f in v.get(k, []):
                        print("  OUT:", f.get("subfolder"), "/", f.get("filename"))
            print("done in %.0fs status=%s" % (time.time() - t0, st.get("status_str")))
            if not st.get("completed"):
                print("messages:", str(st.get("messages"))[:700])
            return
        time.sleep(5)
    print("timeout")


if __name__ == "__main__":
    main()
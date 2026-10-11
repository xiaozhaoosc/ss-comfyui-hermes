"""
Stage 1b: ReActor 把源人脸锁到 Stage1 生成的全身参考图上

source      = input/1todos/005-822807425_18090503405430819_9034340549182780041_n.jpeg
input_image = Stage1 选中的全身候选图
产出        = 既含目标服装(全身) 又含源身份 的 reference_image

用法：
  python tools/wan_stage1b_reactor.py --target "2026-10-10_wb/ref_redraw/cand_00002_.png"
  python tools/wan_stage1b_reactor.py --target ... --source "1todos/xxx.jpeg"
"""
import argparse, json, os, shutil, time, urllib.request, urllib.error, uuid

ROOT = r"d:\ai_projects\ComfyUI"
SERVER = "http://127.0.0.1:8188"

DEFAULT_SOURCE = "1todos/005-822807425_18090503405430819_9034340549182780041_n.jpeg"
DEFAULT_TARGET = "1todos/ref_build/ref_body_cand02.png"


def ensure_in_input(rel):
    """
    LoadImage 只能读 input/ 下的文件。
    接受三种形式：input 相对路径 / output 相对路径 / 绝对路径 → 统一复制进 input 并返回相对路径。
    """
    p = rel.replace("\\", "/")
    # 1) input 下已存在，直接用
    cand = os.path.join(ROOT, "input", p)
    if os.path.exists(cand):
        return p
    # 2) 相对路径：依次尝试 根 / output / input 三个基点
    bases = [ROOT, os.path.join(ROOT, "output"), os.path.join(ROOT, "input")]
    src = p if os.path.isabs(p) else None
    if src is None:
        for b in bases:
            c = os.path.join(b, p)
            if os.path.exists(c):
                src = c
                break
    if src is None or not os.path.exists(src):
        raise FileNotFoundError(f"找不到图像: {rel}")
    dst_dir = os.path.join(ROOT, "input", "1todos", "ref_build")
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(src))
    shutil.copy2(src, dst)
    return "1todos/ref_build/" + os.path.basename(src)


def opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def build(source, target, restore="GFPGANv1.4.pth", visibility=1.0, prefix=None):
    g = {}
    g["1"] = {"class_type": "LoadImage", "inputs": {"image": source}}
    g["2"] = {"class_type": "LoadImage", "inputs": {"image": target}}
    # ReActorFaceSwapOpt: 输出 (IMAGE, FACE_MODEL, IMAGE)
    g["3"] = {"class_type": "ReActorFaceSwapOpt", "_meta": {"title": "ReActor 锁脸"},
              "inputs": {
                  "enabled": True,
                  "input_image": ["2", 0],
                  "source_image": ["1", 0],
                  "swap_model": "inswapper_128.onnx",
                  "facedetection": "retinaface_resnet50",
                  "face_restore_model": restore,
                  "face_restore_visibility": visibility,
                  "codeformer_weight": 0.5,
              }}
    g["4"] = {"class_type": "SaveImage",
              "inputs": {"images": ["3", 0],
                         "filename_prefix": prefix or "2026-10-10_wb/ref_locked/ref_locked"}}
    return g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=DEFAULT_SOURCE)
    ap.add_argument("--target", default=DEFAULT_TARGET)
    ap.add_argument("--restore", default="GFPGANv1.4.pth", choices=["none", "GFPGANv1.4.pth", "codeformer.pth"])
    ap.add_argument("--visibility", type=float, default=1.0)
    ap.add_argument("--prefix", default=None)
    a = ap.parse_args()

    src_rel = ensure_in_input(a.source)
    tgt_rel = ensure_in_input(a.target)
    print("source:", src_rel)
    print("target:", tgt_rel)
    g = build(src_rel, tgt_rel, a.restore, a.visibility, a.prefix)
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
                    print("REJECTED node", nid, info.get("class_type"), ":", str(er.get("details"))[:200])
        except Exception:
            print("REJECTED:", body[:600])
        return
    pid = r["prompt_id"]
    print("submitted", pid, "-> waiting…")
    t0 = time.time()
    while time.time() - t0 < 900:
        try:
            h = json.loads(opener().open(f"{SERVER}/history/{pid}", timeout=20).read().decode())
        except Exception:
            time.sleep(3); continue
        if pid in h:
            st = h[pid].get("status", {})
            for v in h[pid].get("outputs", {}).values():
                for f in v.get("images", []):
                    print("  OUT:", f.get("subfolder"), "/", f.get("filename"))
            print("done in %.0fs status=%s" % (time.time() - t0, st.get("status_str")))
            if not st.get("completed"):
                print("messages:", str(st.get("messages"))[:600])
            return
        time.sleep(3)
    print("timeout")


if __name__ == "__main__":
    main()
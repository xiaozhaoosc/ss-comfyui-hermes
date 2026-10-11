"""
Stage 1: 用 SDXL 重绘「全身站姿参考图」（目标服装：黑色吊带背心 + 黑色紧身裤）

背景：WanAnimateToVideo 没有服装输入，服装只能靠 reference_image 的图像先验决定。
      实测「提示词写服装」无效（图像先验压过文本）→ 所以先重绘参考图（两段式的第一段）。

产出：output/2026-10-10_wb/ref_redraw/ 下若干候选 → 人工挑一张 → Stage1b 用 ReActor 锁脸

用法：
  python tools/wan_stage1_redraw.py                 # 生成 4 张候选
  python tools/wan_stage1_redraw.py --batch 6
  python tools/wan_stage1_redraw.py --outfit "..."  # 换服装
"""
import argparse, json, os, time, urllib.request, urllib.error, uuid

ROOT = r"d:\ai_projects\ComfyUI"
SERVER = "http://127.0.0.1:8188"
CKPT = "RealVisXL_V4.0.safetensors"
VAE = "sdxl_vae.safetensors"

# 9:16 竖屏，需 16 的倍数
W, H = 832, 1472

DEFAULT_OUTFIT = ("wearing a fitted black camisole tank top and black tight leggings, "
                  "sleeveless, showing shoulders and arms")

POS = ("RAW photo, full body shot, entire body from head to toe fully visible, "
       "a beautiful young asian woman standing upright facing camera, {OUTFIT}, "
       "natural relaxed standing pose, arms slightly away from body, "
       "smooth clean studio background, soft even studio lighting, "
       "realistic natural skin texture, sharp focus, 8k uhd, photorealistic, "
       "shot on 85mm f1.4, full length portrait")
NEG = ("cropped, out of frame, cut off head, cut off feet, close-up, portrait headshot, "
       "blurry, low quality, plastic doll, airbrushed, cartoon, anime, "
       "bad anatomy, deformed limbs, extra fingers, mutated hands, "
       "watermark, text, logo, multiple people")


def opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def build(ref_ignored=None, outfit=DEFAULT_OUTFIT, batch=4, seed=20261010, prefix=None):
    g = {}
    g["1"] = {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": CKPT}}
    g["2"] = {"class_type": "VAELoader", "inputs": {"vae_name": VAE}}
    g["3"] = {"class_type": "CLIPTextEncode",
              "inputs": {"text": POS.replace("{OUTFIT}", outfit), "clip": ["1", 1]}}
    g["4"] = {"class_type": "CLIPTextEncode",
              "inputs": {"text": NEG, "clip": ["1", 1]}}
    g["5"] = {"class_type": "EmptyLatentImage",
              "inputs": {"width": W, "height": H, "batch_size": batch}}
    g["6"] = {"class_type": "KSampler",
              "inputs": {"model": ["1", 0], "seed": seed, "steps": 32, "cfg": 5.0,
                         "sampler_name": "dpmpp_2m_sde", "scheduler": "karras",
                         "positive": ["3", 0], "negative": ["4", 0],
                         "latent_image": ["5", 0], "denoise": 1.0}}
    g["7"] = {"class_type": "VAEDecode",
              "inputs": {"samples": ["6", 0], "vae": ["2", 0]}}
    g["8"] = {"class_type": "SaveImage",
              "inputs": {"images": ["7", 0],
                         "filename_prefix": prefix or "2026-10-10_wb/ref_redraw/cand"}}
    return g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outfit", default=DEFAULT_OUTFIT)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--seed", type=int, default=20261010)
    ap.add_argument("--prefix", default=None)
    a = ap.parse_args()

    g = build(outfit=a.outfit, batch=a.batch, seed=a.seed, prefix=a.prefix)
    req = urllib.request.Request(SERVER + "/prompt",
                                 data=json.dumps({"prompt": g, "client_id": str(uuid.uuid4())}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        r = json.loads(opener().open(req, timeout=60).read().decode())
    except urllib.error.HTTPError as e:
        print("REJECTED:", e.read().decode("utf-8", "replace")[:800]); return
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
                print("messages:", str(st.get("messages"))[:500])
            return
        time.sleep(3)
    print("timeout")


if __name__ == "__main__":
    main()
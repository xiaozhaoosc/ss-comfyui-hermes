"""
角色库（character_library）入库工具：把人脸参考图固化为可复用资产。

每个角色 = 一张工作流可直接引用的参考脸（face.<ext>）+ 缩略图 + 512 维身份向量
（RetinaFace 检测 + w600k_r50 识别，均走 insightface model_zoo 直连，禁用的
FaceAnalysis.get() 高层封装不使用——见 tools/h3_rope_common.py E 区纪律）。
备选角度（--alt）一并入库并记录与主脸的余弦相似度，供"同身份多角度"取用。

用法：
  # 入库一个角色（主脸 + 备选角度 + 效果参照成品）
  python tools/char_lib_add.py --face input/ken4/face/gpt/duo.png --char-id char_duo \
      --name "Duo" --alt input/ken4/face/gpt/left.png --alt-note "同一人侧脸照" \
      --ref-output "output/2026-10-12/hitomi_frontal_retest/duo_final/做简简单单的自己，过平平淡淡的生活.mp4" \
      --note "2026-10-12 四脸比对选定的放量用脸"

  # 全库两两身份余弦矩阵（判断哪些参考其实是同一人）
  python tools/char_lib_add.py --matrix

资产落在 character_library/（对齐 garment_library 约定）：index.json 机器可读、
INDEX.md 人读清单、index.html 可视化目录、faces/<char_id>/ 每角色目录。
"""
import argparse
import itertools
import json
import shutil
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).parent.parent
LIB = ROOT / "character_library"
DET_MODEL = "det_10g.onnx"
REC_MODEL = "w600k_r50.onnx"


def _insightface_dir():
    for d in [ROOT / "models" / "insightface" / "buffalo_l",
              ROOT / "models" / "insightface"]:
        if (d / DET_MODEL).exists() and (d / REC_MODEL).exists():
            return d
    raise FileNotFoundError("buffalo_l 模型不完整（需要 %s + %s）" % (DET_MODEL, REC_MODEL))


def _imread(img_path):
    """读图，兼容非 ASCII 路径（cv2.imread 对中文/日文路径返回 None）。"""
    import cv2
    img = cv2.imread(str(img_path))
    if img is None:
        img = cv2.imdecode(np.fromfile(str(img_path), dtype=np.uint8), cv2.IMREAD_COLOR)
    return img


def detect_and_embed(img_path):
    """RetinaFace 取最大脸（bbox+5点+置信度），w600k_r50 算 512 维身份向量"""
    import cv2
    from insightface.model_zoo import get_model
    md = _insightface_dir()
    det = get_model(str(md / DET_MODEL), providers=["CPUExecutionProvider"])
    det.prepare(ctx_id=-1, input_size=(640, 640), det_thresh=0.5)
    rec = get_model(str(md / REC_MODEL), providers=["CPUExecutionProvider"])
    rec.prepare(ctx_id=-1)

    img = _imread(img_path)
    if img is None:
        raise RuntimeError("读图失败: %s" % img_path)
    bboxes, kpss = det.detect(img, input_size=(640, 640), max_num=0)
    if bboxes is None or len(bboxes) == 0:
        raise RuntimeError("未检测到人脸: %s" % img_path)
    bb = np.asarray(bboxes, dtype=np.float32).reshape(-1)
    bb = bb.reshape(-1, 5)[:, :4] if bb.size % 5 == 0 else bb.reshape(-1, 4)[:, :4]
    kp = np.asarray(kpss, dtype=np.float32).reshape(-1, 5, 2)
    area = (bb[:, 2] - bb[:, 0]) * (bb[:, 3] - bb[:, 1])
    i = int(np.argmax(area))
    bbox, kps, score = bb[i], kp[i], float(bboxes.reshape(-1, 5)[i, 4])
    # insightface 的 Recognition.get(img, face) 只取 face.kps 做对齐
    face_obj = SimpleNamespace(kps=kps)
    feat = np.asarray(rec.get(img, face_obj), dtype=np.float32).reshape(-1)
    feat = feat / np.linalg.norm(feat)
    return {"bbox": [float(x) for x in bbox], "score": round(score, 4),
            "img_shape": list(img.shape[:2]), "feat": feat}


def make_thumb(img_path, bbox, dst, size=320):
    """按 bbox 居中扩展裁切正方形人脸缩略图（含发型与肩颈），避免黑边与偏位"""
    import cv2
    img = _imread(img_path)
    h, w = img.shape[:2]
    x1, y1, x2, y2 = bbox
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    face_h = y2 - y1
    face_w = x2 - x1
    # 取脸部高度与宽度的 1.8 倍作为正方形边长，向上微调 5% 留出头顶发型空间
    side = max(int(face_h * 1.8), int(face_w * 1.8))
    cy_adj = cy - face_h * 0.05
    x1_sq = int(cx - side / 2)
    y1_sq = int(cy_adj - side / 2)
    x2_sq = x1_sq + side
    y2_sq = y1_sq + side

    # 限制在图像边界内滑动，避免边缘拉伸伪影
    if x1_sq < 0:
        x1_sq = 0
    elif x1_sq + side > w:
        x1_sq = max(0, w - side)
    x2_sq = min(w, x1_sq + side)

    if y1_sq < 0:
        y1_sq = 0
    elif y1_sq + side > h:
        y1_sq = max(0, h - side)
    y2_sq = min(h, y1_sq + side)

    crop = img[y1_sq:y2_sq, x1_sq:x2_sq]
    thumb = cv2.resize(crop, (size, size), interpolation=cv2.INTER_LANCZOS4)
    cv2.imwrite(str(dst), thumb)




def cos(a, b):
    return round(float(np.dot(a, b)), 4)


def load_index():
    p = LIB / "index.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def save_index(items):
    (LIB / "index.json").write_text(
        json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    build_html(items)
    build_index_md(items)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>角色库目录 character_library</title>
<style>
  body { font-family: "Microsoft YaHei", sans-serif; background: #f5f6f8; color: #222; margin: 24px; }
  h1 { font-size: 20px; }
  .tip { color: #666; font-size: 13px; margin-bottom: 16px; }
  .grid { display: flex; flex-wrap: wrap; gap: 16px; }
  .card { background: #fff; border: 1px solid #e2e4e8; border-radius: 8px; padding: 12px; width: 300px; }
  .card img.thumb { width: 160px; height: 160px; object-fit: cover; border-radius: 6px; display: block; margin: 0 auto 8px; }
  .card .name { font-weight: bold; font-size: 15px; }
  .card .cid { color: #888; font-size: 12px; margin-bottom: 6px; }
  .card .row { font-size: 12px; color: #444; margin: 3px 0; word-break: break-all; }
  .card .path { font-family: Consolas, monospace; background: #f0f1f3; padding: 1px 5px; border-radius: 3px; }
  .alts { display: flex; gap: 6px; margin-top: 6px; flex-wrap: wrap; }
  .alts img { width: 52px; height: 52px; object-fit: cover; border-radius: 4px; }
  .warn { color: #b45309; }
  .ok { color: #15803d; }
</style>
</head>
<body>
<h1>角色库目录（character_library）</h1>
<div class="tip">换脸工作流取脸：引用卡片内的 <b>face 路径</b>（原图直拷，勿用缩略图）｜身份疑问跑 <b>python tools/char_lib_add.py --matrix</b>｜入库：见 README.md</div>
<div class="grid" id="grid"></div>
<script>
const chars = __DATA__;
const grid = document.getElementById("grid");
for (const c of chars) {
  const alts = c.alts.map(a =>
    `<div><img src="${a.file}"><div class="row ${a.cos < 0.6 ? 'warn' : 'ok'}">cos ${a.cos}${a.cos < 0.6 ? ' ⚠存疑' : ''}</div></div>`).join("");
  grid.insertAdjacentHTML("beforeend", `
    <div class="card">
      <img class="thumb" src="${c.thumb}">
      <div class="name">${c.name}</div>
      <div class="cid">${c.cid}｜det ${c.det}</div>
      <div class="row">face：<span class="path">${c.face}</span></div>
      <div class="row">${c.note}</div>
      <div class="alts">${alts}</div>
    </div>`);
}
</script>
</body>
</html>
"""


def build_html(items):
    """从 index.json 重生成可视化目录（双击即用；cos<0.6 的 alt 标存疑）。
    由 save_index 自动调用，入库即刷新，不会静默过期。"""
    chars = []
    for e in items:
        alts = []
        for a in e.get("alts", []):
            thumb = (LIB / e["face"]).parent / "alts" / (Path(a["file"]).stem + "_thumb.png")
            alts.append({"file": str(thumb.relative_to(LIB)).replace("\\", "/")
                         if thumb.exists() else a["file"],
                         "cos": a["cos_to_main"]})
        chars.append({"cid": e["char_id"], "name": e["name"], "det": e["det_score"],
                      "face": e["face"], "thumb": e["thumb"], "note": e.get("note", ""),
                      "alts": alts})
    data = json.dumps(chars, ensure_ascii=False).replace("</", "<\\/")
    (LIB / "index.html").write_text(HTML_TEMPLATE.replace("__DATA__", data), encoding="utf-8")


def _load_vecs(items):
    """载入主脸 + alts 的全部向量，key = (char_id, 显示名)。"""
    vecs = {}
    for e in items:
        cid = e["char_id"]
        emb_path = LIB / e.get("embedding", "")
        if emb_path.exists():
            try:
                vecs[(cid, "main")] = np.load(emb_path)
            except Exception:
                pass
        for al in e.get("alts", []):
            emb = (LIB / e["face"]).parent / "alts" / (Path(al["file"]).stem + "_emb.npy")
            if emb.exists():
                try:
                    vecs[(cid, Path(al["file"]).name)] = np.load(emb)
                except Exception:
                    pass
    return vecs


def _identity_verdict(c):
    if c >= 0.6:
        return "同一身份"
    if c >= 0.4:
        return "⚠️ 存疑，待人工复核"
    return "不同身份"


def build_index_md(items):
    """从 index.json + 向量实测重生成人读清单（由 save_index 自动调用）。
    身份结论按经验阈值判：cos≥0.6 同身份；0.4~0.6 存疑；<0.4 不同身份。"""
    vecs = _load_vecs(items)
    mains = [(e["char_id"], e["name"]) for e in items if (e["char_id"], "main") in vecs]

    lines = [
        "# 角色库清单（INDEX.md）",
        "",
        "> 本文件由 `tools/char_lib_add.py` 入库时自动生成，勿手改；人工结论写进角色的 note/alt-note（会带出）。",
        "> 机器可读版本：`index.json`｜可视化：`index.html`｜身份矩阵：`identity_matrix.json`",
        "> 入库工具：`python tools/char_lib_add.py --face <图> --char-id <id> --name <名> [--alt ...]`",
        "",
        "## 角色总表",
        "",
        "| char_id | 显示名 | 主脸文件 | 检测分 | 备选角度（cos→主脸） | 入库日期 |",
        "|---|---|---|---|---|---|",
    ]
    for e in items:
        alts = "、".join(
            "%s(%.2f)%s" % (Path(a["file"]).name, a["cos_to_main"],
                            "⚠" if a["cos_to_main"] < 0.6 else "")
            for a in e.get("alts", [])) or "—"
        lines.append("| %s | %s | `%s` | %.3f | %s | %s |" % (
            e["char_id"], e["name"], e["face"], e["det_score"], alts, e["added_date"]))
        if e.get("note"):
            lines.append("| ↳ 备注 | %s | | | | |" % e["note"])

    lines += ["", "## 身份矩阵结论（w600k_r50 两两 cos，自动判定）", ""]
    for (ca, _), (cb, _) in itertools.combinations(mains, 2):
        c = cos(vecs[(ca, "main")], vecs[(cb, "main")])
        note = "（接近 0.4 阈值，建议人工目检后再定）" if 0.3 <= c < 0.4 else ""
        lines.append("- **%s ↔ %s：cos %.3f → %s**%s" % (
            ca, cb, c, _identity_verdict(c), note))
    for e in items:
        cid = e["char_id"]
        alt_keys = [(cid, Path(a["file"]).name) for a in e.get("alts", [])
                    if (cid, Path(a["file"]).name) in vecs]
        if len(alt_keys) >= 2:
            pair = [cos(vecs[a], vecs[b])
                    for a, b in itertools.combinations(alt_keys, 2)]
            lines.append("- %s 的 %d 张 alts 互相 cos %.2f~%.2f（%s）" % (
                cid, len(alt_keys), min(pair), max(pair),
                "同一身份家族" if min(pair) >= 0.6 else "含存疑项，见总表 ⚠"))
    for (cid, name), v in vecs.items():
        if name == "main":
            continue
        if (cid, "main") in vecs:
            c = cos(v, vecs[(cid, "main")])
            if c < 0.6:
                lines.append("- ⚠️ %s/%s vs 主脸 cos=%.3f，低于 0.6 → %s" % (
                    cid, name, c, _identity_verdict(c)))

    lines += ["", "## 效果参照成品", ""]
    for e in items:
        for ref in e.get("ref_outputs", []):
            lines.append("- `%s` — %s" % (ref, e["name"]))

    lines += ["", "## 来源", ""]
    for e in items:
        lines.append("- %s ← `%s`" % (e["char_id"], e["source"]))
    lines.append("")

    (LIB / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")


def add_character(a):
    face_path = Path(a.face)
    if not face_path.exists():
        raise FileNotFoundError(face_path)
    char_dir = LIB / "faces" / a.char_id
    (char_dir / "alts").mkdir(parents=True, exist_ok=True)

    info = detect_and_embed(face_path)
    face_dst = char_dir / ("face" + face_path.suffix.lower())
    shutil.copy2(face_path, face_dst)
    make_thumb(face_path, info["bbox"], char_dir / "thumb.png")
    np.save(char_dir / "embedding.npy", info["feat"])

    alts = []
    for alt, note in zip(a.alt or [], a.alt_note or []):
        alt_path = Path(alt)
        ai = detect_and_embed(alt_path)
        alt_dst = char_dir / "alts" / alt_path.name
        shutil.copy2(alt_path, alt_dst)
        make_thumb(alt_path, ai["bbox"], char_dir / "alts" / (alt_path.stem + "_thumb.png"))
        np.save(char_dir / "alts" / (alt_path.stem + "_emb.npy"), ai["feat"])
        alts.append({"file": str(alt_dst.relative_to(LIB)).replace("\\", "/"),
                     "cos_to_main": cos(info["feat"], ai["feat"]),
                     "det_score": ai["score"], "note": note})

    entry = {
        "char_id": a.char_id,
        "name": a.name,
        "face": str(face_dst.relative_to(LIB)).replace("\\", "/"),
        "thumb": str((char_dir / "thumb.png").relative_to(LIB)).replace("\\", "/"),
        "embedding": str((char_dir / "embedding.npy").relative_to(LIB)).replace("\\", "/"),
        "emb_dim": int(info["feat"].size),
        "emb_model": "insightface/w600k_r50",
        "det_model": "insightface/det_10g",
        "det_score": info["score"],
        "face_bbox": info["bbox"],
        "img_shape": info["img_shape"],
        "alts": alts,
        "ref_outputs": a.ref_output or [],
        "source": str(face_path),
        "added_date": time.strftime("%Y-%m-%d"),
        "note": a.note or "",
    }
    items = [e for e in load_index() if e["char_id"] != a.char_id]
    items.append(entry)
    save_index(items)
    print("✅ 入库 %s（%s）｜det_score=%.3f｜alts=%d" % (
        a.char_id, a.name, info["score"], len(alts)))
    for al in alts:
        print("   alt %-24s cos=%.4f  %s" % (Path(al["file"]).name, al["cos_to_main"], al["note"]))


def build_matrix():
    """全库两两身份余弦矩阵：判断哪些参考其实是同一人"""
    items = load_index()
    faces = []
    for e in items:
        faces.append((e["char_id"], "main", LIB / e["embedding"]))
        for al in e.get("alts", []):
            emb = (LIB / e["face"]).parent / "alts" / (Path(al["file"]).stem + "_emb.npy")
            faces.append((e["char_id"], Path(al["file"]).name, emb))
    names = ["%s/%s" % (c, t) for c, t, _ in faces]
    vecs = [np.load(p) for _, _, p in faces]
    m = [[cos(vecs[i], vecs[j]) for j in range(len(vecs))] for i in range(len(vecs))]
    out = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"),
           "model": "insightface/w600k_r50", "faces": names, "cos_matrix": m}
    (LIB / "identity_matrix.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(" faces".ljust(28) + "".join(n[:12].rjust(14) for n in names))
    for i, n in enumerate(names):
        print(n[:26].ljust(28) + "".join(("%.3f" % m[i][j]).rjust(14) for j in range(len(names))))
    print("\n→ character_library/identity_matrix.json（cos≥0.6 经验上同身份；≥0.4 疑似，需人工确认）")


def main():
    ap = argparse.ArgumentParser(description="角色库入库工具")
    ap.add_argument("--face", help="主参考脸图片路径")
    ap.add_argument("--char-id", help="角色 ID（如 char_duo）")
    ap.add_argument("--name", help="显示名")
    ap.add_argument("--alt", action="append", help="备选角度图片（可多次）")
    ap.add_argument("--alt-note", action="append", help="与 --alt 顺序对应的说明")
    ap.add_argument("--ref-output", action="append", help="效果参照成品路径（可多次）")
    ap.add_argument("--note", help="备注")
    ap.add_argument("--matrix", action="store_true", help="全库两两身份余弦矩阵")
    a = ap.parse_args()

    LIB.mkdir(parents=True, exist_ok=True)
    if a.matrix:
        build_matrix()
        return
    if not (a.face and a.char_id and a.name):
        ap.error("入库需要 --face/--char-id/--name")
    add_character(a)


if __name__ == "__main__":
    main()

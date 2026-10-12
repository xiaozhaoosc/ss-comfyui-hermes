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


def detect_and_embed(img_path):
    """RetinaFace 取最大脸（bbox+5点+置信度），w600k_r50 算 512 维身份向量"""
    import cv2
    from insightface.model_zoo import get_model
    md = _insightface_dir()
    det = get_model(str(md / DET_MODEL), providers=["CPUExecutionProvider"])
    det.prepare(ctx_id=-1, input_size=(640, 640), det_thresh=0.5)
    rec = get_model(str(md / REC_MODEL), providers=["CPUExecutionProvider"])
    rec.prepare(ctx_id=-1)

    img = cv2.imread(str(img_path))
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
    """按 bbox 裁脸（外扩 35%）生成缩略图"""
    import cv2
    img = cv2.imread(str(img_path))
    h, w = img.shape[:2]
    x1, y1, x2, y2 = bbox
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    bw, bh = (x2 - x1) * 1.35, (y2 - y1) * 1.35
    x1, y1 = max(0, int(cx - bw / 2)), max(0, int(cy - bh / 2))
    x2, y2 = min(w, int(cx + bw / 2)), min(h, int(cy + bh / 2))
    crop = img[y1:y2, x1:x2]
    side = max(crop.shape[:2])
    square = np.zeros((side, side, 3), dtype=np.uint8)
    square[:crop.shape[0], :crop.shape[1]] = crop
    square = cv2.resize(square, (size, size))
    cv2.imwrite(str(dst), square)


def cos(a, b):
    return round(float(np.dot(a, b)), 4)


def load_index():
    p = LIB / "index.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def save_index(items):
    (LIB / "index.json").write_text(
        json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")


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

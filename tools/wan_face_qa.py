"""对比 源脸 / Stage2成片 / Stage3锁脸 的身份一致性（灰度像素余弦 + 检测率）

硬约束（见 MEMORY.md）：禁用 insightface FaceAnalysis.get()（native 崩溃），
直连 RetinaFace det_10g.onnx；该进程不要 import torch。
"""
import cv2, numpy as np, sys

DET = r"C:\Users\kenzhao\.insightface\models\buffalo_l\det_10g.onnx"


def load(p):
    return cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)


def make_det():
    from insightface.model_zoo import get_model
    d = get_model(DET)
    d.prepare(-1, input_size=(640, 640), det_thresh=0.5)
    return d


def emb(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32).flatten()
    g -= g.mean()
    return g / (np.linalg.norm(g) + 1e-8)


def face_of(det, img):
    bb, _ = det.detect(img)
    if not len(bb):
        return None
    x1, y1, x2, y2 = [int(v) for v in bb[0][:4]]
    x1, y1 = max(0, x1), max(0, y1)
    c = img[y1:y2, x1:x2]
    if not c.size:
        return None
    return cv2.resize(c, (112, 112))


def scan_video(det, path, every=1):
    c = cv2.VideoCapture(path)
    faces, i = [], 0
    while True:
        ok, fr = c.read()
        if not ok:
            break
        if i % every == 0:
            f = face_of(det, fr)
            if f is not None:
                faces.append((i, f))
        i += 1
    c.release()
    return faces, i


def main():
    src_path = sys.argv[1]
    vids = sys.argv[2:]
    det = make_det()
    src_face = face_of(det, load(src_path))
    if src_face is None:
        print("源图未检到人脸"); return
    cv2.imwrite("output/2026-10-10_wb/_qa/src_face112.png", src_face)
    se = emb(src_face)
    print("参照(源图脸) 已保存 -> _qa/src_face112.png")
    print()
    for v in vids:
        fs, total = scan_video(det, v)
        if not fs:
            print("%-60s 未检到人脸" % v.split('/')[-1][:60]); continue
        sims = [float(np.dot(emb(f), se)) for _, f in fs]
        print("%-56s 帧=%-4d 检出=%-4d(%.0f%%) identity mean=%.3f min=%.3f" % (
            v.split('/')[-1][:56], total, len(fs), 100 * len(fs) / total,
            float(np.mean(sims)), float(np.min(sims))))


if __name__ == "__main__":
    main()

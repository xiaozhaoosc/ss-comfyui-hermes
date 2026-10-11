import io, glob, os
from PIL import Image
import numpy as np

out = []
for p in sorted(glob.glob(r"D:\ai_projects\ComfyUI\output\zimage_test_*.png")):
    im = Image.open(p).convert("RGB")
    a = np.asarray(im).astype(np.float32) / 255.0
    gray = a.mean(axis=2)
    # 局部方差（锐度粗判）
    lap = np.abs(np.diff(gray, axis=0)).mean() + np.abs(np.diff(gray, axis=1)).mean()
    out.append("%s" % os.path.basename(p))
    out.append("  size=%s  mean=%.3f  std=%.3f  min=%.3f  max=%.3f" % (
        im.size, gray.mean(), gray.std(), gray.min(), gray.max()))
    out.append("  per-channel mean R/G/B = %.3f / %.3f / %.3f" % (
        a[:, :, 0].mean(), a[:, :, 1].mean(), a[:, :, 2].mean()))
    out.append("  gradient(sharpness proxy)=%.4f" % lap)
    out.append("  判定: %s" % ("全黑/全白异常" if gray.std() < 0.02 else "有正常图像内容"))

with io.open(r"D:\ai_projects\ComfyUI\_img_stat.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("ok")

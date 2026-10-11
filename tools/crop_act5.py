import cv2
import numpy as np
from PIL import Image, ImageOps
import os

img_path = r"C:\Users\kenzhao\.gemini\antigravity\brain\f970c72f-40d0-4e19-b5f8-9f70bb48ecc5\act5_storyboard_grid_1791126353152.jpg"
out_dir = r"D:\ai_projects\ComfyUI\input"

im_bgr = cv2.imread(img_path)
gray = cv2.cvtColor(im_bgr, cv2.COLOR_BGR2GRAY)
H, W = gray.shape

edges = cv2.Canny(gray, 50, 150)
contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

boxes = []
for cnt in contours:
    x, y, w, h = cv2.boundingRect(cnt)
    # Check if aspect ratio is roughly 16:9 and area is suitable for 3x3 cell
    if w > 350 and h > 180 and w < W * 0.38 and h < H * 0.38:
        boxes.append((x, y, w, h))

print(f"Found {len(boxes)} candidate boxes for Act 5")
if len(boxes) < 8:
    # Fallback to precise grid division (3x3 grid across 1376x768):
    cell_w = W / 3.0
    cell_h = H / 3.0
    boxes = []
    for r in range(3):
        for c in range(3):
            boxes.append((int(c * cell_w), int(r * cell_h), int(cell_w), int(cell_h)))

# Sort boxes top-to-bottom, left-to-right
boxes = sorted(boxes, key=lambda b: (b[1] // 200, b[0]))
print(f"Total sorted boxes: {len(boxes)}")

pil_img = Image.open(img_path).convert("RGB")
shots = [34, 35, 36, 37, 38, 39, 40, 41]

for i, (x, y, w, h) in enumerate(boxes[:8]):
    shot_id = shots[i]
    # Inset slightly (6px) to remove the black border line
    crop_box = (x + 6, y + 6, x + w - 6, y + h - 6)
    cropped = pil_img.crop(crop_box)
    fitted = ImageOps.fit(cropped, (1376, 768), method=Image.Resampling.LANCZOS)
    out_fn = f"yang_ep01_shot{shot_id}.jpg"
    out_path = os.path.join(out_dir, out_fn)
    fitted.save(out_path, quality=95)
    print(f"Saved Shot {shot_id}: {out_path} ({fitted.size})")

import cv2
import numpy as np
from PIL import Image, ImageOps
import os

img_path = r"C:\Users\kenzhao\.gemini\antigravity\brain\f970c72f-40d0-4e19-b5f8-9f70bb48ecc5\act4_storyboard_grid_1791117817180.jpg"
out_dir = r"D:\ai_projects\ComfyUI\input"

im_bgr = cv2.imread(img_path)
gray = cv2.cvtColor(im_bgr, cv2.COLOR_BGR2GRAY)
H, W = gray.shape

# Threshold black border
# The 6 image panels have distinct black border lines
edges = cv2.Canny(gray, 50, 150)
contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

boxes = []
for cnt in contours:
    x, y, w, h = cv2.boundingRect(cnt)
    # Check if aspect ratio is roughly 16:9 and area is substantial
    if w > 300 and h > 180 and w < W * 0.4 and h < H * 0.45:
        boxes.append((x, y, w, h))

print(f"Found {len(boxes)} candidate boxes")
if len(boxes) < 6:
    # Fallback to manual grid calculation:
    # 2 rows, 3 columns:
    # Row 1 picture box is roughly y: 38 to 300
    # Row 2 picture box is roughly y: 405 to 667
    # Col 1: x: 26 to 455
    # Col 2: x: 472 to 901
    # Col 3: x: 918 to 1347
    boxes = [
        (26, 38, 429, 262),
        (472, 38, 429, 262),
        (918, 38, 429, 262),
        (26, 405, 429, 262),
        (472, 405, 429, 262),
        (918, 405, 429, 262),
    ]

# Sort boxes top-to-bottom, left-to-right
boxes = sorted(boxes, key=lambda b: (b[1] // 200, b[0]))
print("Boxes sorted:")
for i, b in enumerate(boxes):
    print(f"  Panel {i+1}: {b}")

pil_img = Image.open(img_path).convert("RGB")
shots = [28, 29, 30, 31, 32, 33]

for i, (x, y, w, h) in enumerate(boxes[:6]):
    shot_id = shots[i]
    # Inset slightly (4px) to remove the black border line itself
    crop_box = (x + 5, y + 5, x + w - 5, y + h - 5)
    cropped = pil_img.crop(crop_box)
    fitted = ImageOps.fit(cropped, (1376, 768), method=Image.Resampling.LANCZOS)
    out_fn = f"yang_ep01_shot{shot_id}.jpg"
    out_path = os.path.join(out_dir, out_fn)
    fitted.save(out_path, quality=95)
    print(f"Saved Shot {shot_id}: {out_path} ({fitted.size})")

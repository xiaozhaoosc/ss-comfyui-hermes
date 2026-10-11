import os
from PIL import Image

grid_image_path = r"C:\Users\kenzhao\.gemini\antigravity\brain\6bb43a19-f574-41a1-a679-7d82b1966d15\yang_ep03_grid01_1791472115813.jpg"
out_dir = r"d:\ai_projects\ComfyUI\output\2026-10-08\yangjiajiang_ep03\flow_pilot"
os.makedirs(out_dir, exist_ok=True)

img = Image.open(grid_image_path)
w, h = img.size
print(f"Original grid image size: {w}x{h}")

# The image is 3x3 grid.
# Each cell takes approximately w/3 in width, h/3 in height.
# In each cell, the top ~75% is the drawing and the bottom ~25% is text label with a black border.
# Let's calculate precise bounding boxes to extract only the artwork inside each border!

col_w = w / 3.0
row_h = h / 3.0

# Margin offsets inside each 1/3 cell (percentage of cell size)
# Based on visual inspection:
# cell borders: ~3% padding from cell edges
# artwork: top 5% to ~73% of cell height, 4% to 96% of cell width

for r in range(3):
    for c in range(3):
        shot_id = r * 3 + c + 1
        x_min = int(c * col_w + col_w * 0.04)
        x_max = int(c * col_w + col_w * 0.96)
        y_min = int(r * row_h + row_h * 0.04)
        y_max = int(r * row_h + row_h * 0.74) # exclude caption text
        
        panel = img.crop((x_min, y_min, x_max, y_max))
        
        # Save as 9:16 or original aspect ratio
        # Let's save standard start frame
        out_path = os.path.join(out_dir, f"shot0{shot_id}.jpg")
        panel.save(out_path, quality=95)
        print(f"Saved Shot {shot_id:02d} ({panel.size[0]}x{panel.size[1]}) -> {out_path}")

print("All 9 pilot shots cropped successfully!")

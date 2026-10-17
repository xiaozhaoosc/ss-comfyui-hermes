# -*- coding: utf-8 -*-
"""Nine-grid Character Turnaround Sheet Slicer.
Slices a 9:16 3x3 matrix character sheet into 9 distinct standalone view assets.
"""
from pathlib import Path
from PIL import Image

VIEW_NAMES = [
    ("01_front", "1. 正视全景 (Front View)"),
    ("02_three_quarter", "2. 四分之三正面 (Three-Quarter Front)"),
    ("03_side_profile", "3. 侧颜正侧 (Side Profile)"),
    ("04_three_quarter_back", "4. 四分之三背面 (Three-Quarter Back)"),
    ("05_back", "5. 正背面视角 (Back View)"),
    ("06_perspective_dynamic", "6. 低角度仰视透视 (Low-Angle Perspective)"),
    ("07_portrait_face", "7. 极致正脸肖像特写 (Extreme Close-up Face Portrait)"),
    ("08_portrait_45deg", "8. 45度侧颜微侧特写 (45-Degree Profile Glance)"),
    ("09_hair_ear_detail", "9. 发丝耳廓结构特写 (Hair Strands & Ear Detail)")
]

def slice_9view_sheet(sheet_img_path, output_dir):
    sheet_path = Path(sheet_img_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(sheet_path) as im:
        w, h = im.size
        # 3 columns, 3 rows
        cw = w / 3.0
        ch = h / 3.0

        sliced_files = []
        for row in range(3):
            for col in range(3):
                idx = row * 3 + col
                tag, desc = VIEW_NAMES[idx]
                box = (
                    int(round(col * cw)),
                    int(round(row * ch)),
                    int(round((col + 1) * cw)),
                    int(round((row + 1) * ch))
                )
                sub_img = im.crop(box)
                out_file = out_dir / f"{tag}.png"
                sub_img.save(out_file, format="PNG")
                sliced_files.append({
                    "tag": tag,
                    "desc": desc,
                    "file": str(out_file),
                    "size": sub_img.size
                })
        return sliced_files

if __name__ == "__main__":
    target = Path("character_library/faces/char_ye_muchen_2100_01/face.png")
    if target.exists():
        res = slice_9view_sheet(target, "character_library/faces/char_ye_muchen_2100_01/views")
        print(f"Successfully sliced {len(res)} views:")
        for r in res:
            print(f"  - {r['tag']} ({r['desc']}) -> {r['size']}")

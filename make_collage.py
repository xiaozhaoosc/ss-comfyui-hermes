
from PIL import Image
import os

image_paths = [
    ('1. IDM-VTON换装结果', 'd:/ai_projects/ComfyUI/output/test_idm_vton_v3_20260814_00001_.png'),
    ('2. DensePose姿态图', 'd:/ai_projects/ComfyUI/output/test_idm_vton_pose_v3_20260814_00001_.png'),
    ('3. 服装Mask图', 'd:/ai_projects/ComfyUI/output/test_idm_vton_mask_v3_20260814_00001_.png'),
    ('4. MimicMotion首帧', 'd:/ai_projects/ComfyUI/output/mimicmotion_test_short_v2_00001.png'),
    ('5. 逐帧换装结果_05', 'd:/ai_projects/ComfyUI/output/tryon_result_00005_.png'),
    ('6. 换脸+换装组合', 'd:/ai_projects/ComfyUI/output/test_faceswap_v2_20260814.png'),
    ('7. IDM-VTON输入原图', 'd:/ai_projects/ComfyUI/input/pics/test_frame_001.png'),
    ('8. MimicMotion参考Ken', 'd:/ai_projects/ComfyUI/input/todo/face/ken4.png')
]

# 每行4张，共2行
cols, rows = 4, 2
# 每张缩略图的尺寸 (保持比例，宽度统一300)
thumb_w = 300

images = []
for label, path in image_paths:
    try:
        img = Image.open(path)
        if img.mode == 'RGBA':
            bg = Image.new('RGB', img.size, (255,255,255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        # 缩放
        w, h = img.size
        ratio = thumb_w / w
        thumb_h = int(h * ratio)
        img = img.resize((thumb_w, thumb_h), Image.LANCZOS)
        images.append((label, img))
        print(f"Loaded: {label} -> {thumb_w}x{thumb_h}")
    except Exception as e:
        print(f"Error loading {label}: {e}")

# 计算画布大小
max_h_per_row = max(img.size[1] for _, img in images[:cols])
spacing = 40  # 标签空间+间距
margin = 20

total_w = cols * thumb_w + (cols-1) * spacing + margin * 2
total_h = rows * (max_h_per_row + 60) + (rows-1) * spacing + margin * 2

canvas = Image.new('RGB', (total_w, total_h), (240, 240, 240))

from PIL import ImageDraw, ImageFont
# 尝试加载字体
font = None
try:
    font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 20)
except:
    try:
        font = ImageFont.truetype('C:/Windows/Fonts/simhei.ttf', 20)
    except:
        font = ImageFont.load_default()

draw = ImageDraw.Draw(canvas)

for idx, (label, img) in enumerate(images):
    r = idx // cols
    c = idx % cols
    x = margin + c * (thumb_w + spacing)
    y = margin + r * (max_h_per_row + 60 + spacing)
    
    # 画边框
    border_w = thumb_w + 4
    border_h = max_h_per_row + 4
    draw.rectangle([x-2, y-2, x-2+border_w, y-2+border_h], fill=(255,255,255), outline=(180,180,180))
    
    # 粘贴图片 (居中)
    img_w, img_h = img.size
    offset_y = (max_h_per_row - img_h) // 2
    canvas.paste(img, (x, y + offset_y))
    
    # 画标签
    label_y = y + max_h_per_row + 8
    draw.text((x, label_y), label, fill=(40, 40, 40), font=font)
    # 画尺寸信息
    orig_path = image_paths[idx][1]
    orig_img = Image.open(orig_path)
    size_text = f"{orig_img.size[0]}x{orig_img.size[1]}"
    draw.text((x, label_y + 28), size_text, fill=(100, 100, 100), font=font)
    orig_img.close()

out_path = 'd:/ai_projects/ComfyUI/output_collage.png'
canvas.save(out_path, quality=95)
print(f"Collage saved: {out_path}, size: {canvas.size}")

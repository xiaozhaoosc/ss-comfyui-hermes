"""生成正确的上衣遮罩（排除头部）"""
import os, sys, numpy as np, cv2
from PIL import Image

sys.path.insert(0, r'D:\ai_projects\ComfyUI\custom_nodes\ComfyUI-IDM-VTON')
import onnxruntime as ort

parsing_path = 'models/IDM-VTON/humanparsing/parsing_atr.onnx'
session = ort.InferenceSession(parsing_path, providers=['CPUExecutionProvider'])
print(f"Provider: {session.get_providers()}")

person = Image.open('input/vton/person.png').convert('RGB')
orig_w, orig_h = person.size
print(f"原图: {orig_w}x{orig_h}")

img_resized = person.resize((512, 512), Image.BILINEAR)
img_np = np.array(img_resized).astype(np.float32) / 255.0
img_np = (img_np - np.array([0.406, 0.456, 0.485])) / np.array([0.225, 0.224, 0.229])
img_np = img_np.transpose(2, 0, 1)[np.newaxis].astype(np.float32)

input_name = session.get_inputs()[0].name
output = session.run(None, {input_name: img_np})
raw = output[0]  # shape: (1, 18, 128, 128) 或 (18, 128, 128)
print(f"Raw output shape: {raw.shape}")

# 如果是概率图 (N, C, H, W)，取 argmax 得到标签图
if raw.ndim == 4:
    parsing = np.argmax(raw[0], axis=0).astype(np.int32)  # (H, W)
elif raw.ndim == 3:
    parsing = np.argmax(raw, axis=0).astype(np.int32)
else:
    parsing = raw.squeeze().astype(np.int32)
print(f"Parsing shape: {parsing.shape}")

label_names = {0:'BG', 1:'Hat', 2:'Hair', 3:'Glove', 4:'Upper-clothes', 
               5:'Dress', 6:'Coat', 7:'Socks', 8:'Pants', 9:'Jumpsuits',
               10:'Scarf', 11:'Skirt', 12:'Face', 13:'L-arm', 14:'R-arm',
               15:'L-leg', 16:'R-leg', 17:'L-shoe', 18:'R-shoe'}

labels, counts = np.unique(parsing, return_counts=True)
print("\n标签分布:")
for l, c in zip(labels, counts):
    name = label_names.get(l, f'X{l}')
    print(f"  {name:15s}: {c:>6d} px ({c*100/512/512:.1f}%)")

# 只保留上衣：4(Upper-clothes) + 6(Coat)
clothing_labels = [4, 6]
mask = np.isin(parsing, clothing_labels).astype(np.uint8) * 255
clothing_pixels = np.sum(mask > 0)
print(f"\n上衣像素: {clothing_pixels} ({clothing_pixels*100/512/512:.1f}%)")

# 检查头部是否被包含
face_mask = (parsing == 12).astype(np.uint8) * 255
face_overlap = np.sum((mask > 0) & (face_mask > 0))
print(f"面部与上衣重叠: {face_overlap} px")

# 形态学平滑
kernel = np.ones((5, 5), np.uint8)
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

# 保存
mask_uint8 = np.ascontiguousarray(mask.astype(np.uint8))
mask_384 = Image.fromarray(mask_uint8, mode='L').resize((384, 512), Image.NEAREST)
mask_384.save('input/todo/vton_test/mask_fixed_384x512.png')

mask_orig = Image.fromarray(mask_uint8, mode='L').resize((orig_w, orig_h), Image.NEAREST)
mask_orig.save('input/vton/mask_fixed.png')

print(f"\n已保存:")
print(f"  input/vton/mask_fixed.png ({orig_w}x{orig_h})")
print(f"  input/todo/vton_test/mask_fixed_384x512.png (384x512)")
print("[DONE]")

"""修复 mask：模糊边缘 + 排除头部区域"""
import numpy as np, cv2
from PIL import Image

# 加载已生成的 mask
mask = np.array(Image.open('input/todo/vton_test/mask_fixed_384x512.png').convert('L'))
print(f"原始 mask: {mask.shape}, 白像素: {np.sum(mask > 0)}")

# 排除上半部分（头部区域通常在图片上半部分）
h, w = mask.shape
# 保留 y > h*0.25 的区域（排除头部）
head_cutoff = int(h * 0.25)
mask[:head_cutoff, :] = 0
print(f"排除头部后: 白像素: {np.sum(mask > 0)}")

# 排除面积太小的连通区域（噪声）
num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
min_area = 200  # 最小面积阈值
for i in range(1, num_labels):
    if stats[i, cv2.CC_STAT_AREA] < min_area:
        mask[labels == i] = 0
print(f"去噪后: 白像素: {np.sum(mask > 0)}")

# 形态学操作
kernel = np.ones((5, 5), np.uint8)
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=3)
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)

# 高斯模糊边缘（渐变过渡）
mask_blur = cv2.GaussianBlur(mask, (21, 21), 0)

# 二值化后再模糊（保留主体区域清晰，边缘渐变）
_, mask_binary = cv2.threshold(mask_blur, 127, 255, cv2.THRESH_BINARY)
mask_feathered = cv2.GaussianBlur(mask_binary, (15, 15), 0)

print(f"渐变后: 白像素(>128): {np.sum(mask_feathered > 128)}")

# 保存
Image.fromarray(mask_feathered).save('input/todo/vton_test/mask_feathered_384x512.png')
print("已保存: input/todo/vton_test/mask_feathered_384x512.png")

# 对比保存
Image.fromarray(mask).save('input/todo/vton_test/mask_binary_384x512.png')
print("已保存: input/todo/vton_test/mask_binary_384x512.png (二值)")
print("[DONE]")

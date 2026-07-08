#!/usr/bin/env python3
"""
预处理：为每个视频帧生成遮挡区域 mask。
三种遮挡类型：
1. 数字马赛克 - 检测块状像素化区域
2. 物理遮挡(手机/手) - 检测非肤色的大面积遮挡
3. 无头画面 - 返回特殊标记
"""
import cv2
import numpy as np
import os
import sys

INPUT_DIR = r"D:\ai_projects\ComfyUI\input\ra_classify"
MASK_DIR = r"D:\ai_projects\ComfyUI\input\ra_masks"
os.makedirs(MASK_DIR, exist_ok=True)

def detect_face_region(frame):
    """估计面部区域（上半部分中间区域）"""
    h, w = frame.shape[:2]
    # Face is typically in the upper 40% of the frame, centered
    face_y1 = int(h * 0.05)
    face_y2 = int(h * 0.45)
    face_x1 = int(w * 0.2)
    face_x2 = int(w * 0.8)
    return face_x1, face_y1, face_x2, face_y2

def detect_mosaic_mask(frame):
    """检测数字马赛克区域的 mask"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    x1, y1, x2, y2 = detect_face_region(frame)
    face_region = gray[y1:y2, x1:x2]
    
    # Detect blocky patterns
    block_size = 8
    mask_blocks = np.zeros_like(face_region, dtype=np.uint8)
    
    for by in range(0, face_region.shape[0] - block_size, block_size):
        for bx in range(0, face_region.shape[1] - block_size, block_size):
            block = face_region[by:by+block_size, bx:bx+block_size]
            # Mosaic blocks have low internal variance
            if block.std() < 10:
                # Check if it's part of a grid pattern (mosaic)
                # by checking contrast with neighboring blocks
                mask_blocks[by:by+block_size, bx:bx+block_size] = 255
    
    # Dilate to fill gaps
    kernel = np.ones((5, 5), np.uint8)
    mask_blocks = cv2.dilate(mask_blocks, kernel, iterations=2)
    mask_blocks = cv2.GaussianBlur(mask_blocks, (11, 11), 0)
    
    # Create full-size mask
    full_mask = np.zeros((h, w), dtype=np.uint8)
    full_mask[y1:y2, x1:x2] = mask_blocks
    
    return full_mask

def detect_occlusion_mask(frame):
    """检测物理遮挡区域（手机/手）的 mask"""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = detect_face_region(frame)
    face_region = hsv[y1:y2, x1:x2]
    
    # Skin color range in HSV
    lower_skin = np.array([0, 20, 70])
    upper_skin = np.array([20, 255, 255])
    skin_mask = cv2.inRange(face_region, lower_skin, upper_skin)
    
    # Non-skin area in face region is likely occlusion
    occlusion_mask = cv2.bitwise_not(skin_mask)
    
    # Clean up
    kernel = np.ones((7, 7), np.uint8)
    occlusion_mask = cv2.morphologyEx(occlusion_mask, cv2.MORPH_CLOSE, kernel)
    occlusion_mask = cv2.GaussianBlur(occlusion_mask, (11, 11), 0)
    
    full_mask = np.zeros((h, w), dtype=np.uint8)
    full_mask[y1:y2, x1:x2] = occlusion_mask
    
    return full_mask

def classify_and_mask(frame):
    """分类并生成 mask"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    x1, y1, x2, y2 = detect_face_region(frame)
    face_region = gray[y1:y2, x1:x2]
    
    # Check if face region has skin
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    face_hsv = hsv[y1:y2, x1:x2]
    lower_skin = np.array([0, 20, 70])
    upper_skin = np.array([20, 255, 255])
    skin_mask = cv2.inRange(face_hsv, lower_skin, upper_skin)
    skin_ratio = np.sum(skin_mask > 0) / skin_mask.size
    
    # Check for mosaic blocks
    block_size = 8
    low_var_count = 0
    total_blocks = 0
    for by in range(0, face_region.shape[0] - block_size, block_size):
        for bx in range(0, face_region.shape[1] - block_size, block_size):
            block = face_region[by:by+block_size, bx:bx+block_size]
            total_blocks += 1
            if block.std() < 10:
                low_var_count += 1
    low_var_ratio = low_var_count / total_blocks if total_blocks > 0 else 0
    
    # Classify
    if skin_ratio < 0.03 and np.std(face_region) < 30:
        return 'noface', None
    elif low_var_ratio > 0.3:
        mask = detect_mosaic_mask(frame)
        return 'mosaic', mask
    else:
        mask = detect_occlusion_mask(frame)
        return 'occlusion', mask

# Process all frames
for fname in sorted(os.listdir(INPUT_DIR)):
    if not fname.endswith('.jpg'):
        continue
    path = os.path.join(INPUT_DIR, fname)
    frame = cv2.imread(path)
    if frame is None:
        print(f"SKIP: {fname} (can't read)")
        continue
    
    category, mask = classify_and_mask(frame)
    
    if mask is not None:
        mask_path = os.path.join(MASK_DIR, fname.replace('.jpg', '_mask.png'))
        cv2.imwrite(mask_path, mask)
        print(f"  {category:10s} {fname[:35]:35s} → mask saved ({np.sum(mask>0)/mask.size*100:.1f}% masked)")
    else:
        print(f"  {category:10s} {fname[:35]:35s} → no mask (noface)")

print(f"\nMasks saved to {MASK_DIR}")
print(f"Total: {len([f for f in os.listdir(MASK_DIR) if f.endswith('.png')])} masks")

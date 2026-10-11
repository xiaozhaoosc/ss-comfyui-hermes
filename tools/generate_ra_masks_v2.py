#!/usr/bin/env python3
"""
精确检测遮挡区域 mask v2。
针对三种遮挡类型分别优化：
- 白色圆形马赛克(带问号): 检测高亮度圆形区域
- 黑白格子马赛克: 检测块状像素化
- 物理遮挡(手机/手): 检测非肤色的大面积暗区
"""
import cv2
import numpy as np
import os

INPUT_DIR = r"D:\ai_projects\ComfyUI\input\ra_classify"
MASK_DIR = r"D:\ai_projects\ComfyUI\input\ra_masks"
os.makedirs(MASK_DIR, exist_ok=True)

def detect_white_circle_mosaic(frame):
    """检测白色圆形马赛克（带问号的那种）"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    
    # Focus on upper 45% of frame
    roi = gray[:int(h*0.45), :]
    
    # Detect bright circular regions
    # White mosaic circle will be significantly brighter than surroundings
    blurred = cv2.GaussianBlur(roi, (15, 15), 0)
    
    # Threshold for bright areas
    _, bright = cv2.threshold(blurred, 200, 255, cv2.THRESH_BINARY)
    
    # Find contours
    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    mask = np.zeros_like(gray)
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 500:  # Minimum size for face mosaic
            x, y, bw, bh = cv2.boundingRect(cnt)
            aspect = bw / bh if bh > 0 else 0
            # Circle should have aspect ratio close to 1
            if 0.5 < aspect < 2.0:
                # Create slightly expanded mask for clean inpainting
                cx, cy = x + bw//2, y + bh//2
                radius = max(bw, bh) // 2 + 10
                cv2.circle(mask, (cx, cy), radius, 255, -1)
    
    return mask

def detect_grid_mosaic(frame):
    """检测黑白格子马赛克"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    roi = gray[:int(h*0.45), :]
    
    # Detect blocky patterns by looking at local variance
    block_size = 8
    mask_roi = np.zeros_like(roi)
    
    for by in range(0, roi.shape[0] - block_size, block_size):
        for bx in range(0, roi.shape[1] - block_size, block_size):
            block = roi[by:by+block_size, bx:bx+block_size]
            # Mosaic blocks have very low internal variance
            if block.std() < 8:
                # But also check that it's part of a grid (not just flat background)
                # by checking if neighboring blocks have different means
                mean_val = block.mean()
                # Check if this is in the face area (not background)
                if 50 < bx < roi.shape[1] - 50:  # Not at edges
                    mask_roi[by:by+block_size, bx:bx+block_size] = 255
    
    # Clean up - remove small isolated regions
    kernel = np.ones((5, 5), np.uint8)
    mask_roi = cv2.morphologyEx(mask_roi, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask_roi = cv2.morphologyEx(mask_roi, cv2.MORPH_OPEN, kernel)
    
    # Find largest connected component (should be the mosaic)
    contours, _ = cv2.findContours(mask_roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        largest = max(contours, key=cv2.contourArea)
        mask_roi = np.zeros_like(roi)
        cv2.drawContours(mask_roi, [largest], -1, 255, -1)
        # Expand slightly
        mask_roi = cv2.dilate(mask_roi, kernel, iterations=3)
    
    mask = np.zeros_like(gray)
    mask[:int(h*0.45), :] = mask_roi
    return mask

def detect_phone_occlusion(frame):
    """检测手机/手物理遮挡"""
    h, w = frame.shape[:2]
    roi = frame[:int(h*0.45), :, :]
    
    # Convert to HSV
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    
    # Skin color detection
    lower_skin = np.array([0, 20, 70])
    upper_skin = np.array([20, 255, 255])
    skin = cv2.inRange(hsv, lower_skin, upper_skin)
    
    # Also detect extended skin range
    lower_skin2 = np.array([0, 10, 50])
    upper_skin2 = np.array([25, 255, 255])
    skin2 = cv2.inRange(hsv, lower_skin2, upper_skin2)
    skin = cv2.bitwise_or(skin, skin2)
    
    # The phone/hand is the non-skin area in the face region
    # But we need to exclude background (gray wall)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    
    # Non-skin AND not background (background is typically very uniform gray)
    bg_mask = cv2.inRange(gray, 180, 230)  # Gray background
    
    # Dark non-skin areas (phone, dark clothing near face)
    dark_mask = cv2.inRange(gray, 0, 80)
    
    # Occlusion = dark area in face region that's not background
    occlusion = cv2.bitwise_and(dark_mask, cv2.bitwise_not(bg_mask))
    
    # Also consider non-skin, non-background areas
    non_skin = cv2.bitwise_not(skin)
    non_bg = cv2.bitwise_not(bg_mask)
    potential_occlusion = cv2.bitwise_and(non_skin, non_bg)
    
    # Combine
    occlusion = cv2.bitwise_or(occlusion, potential_occlusion)
    
    # Only keep the central portion (where face should be)
    center_mask = np.zeros_like(roi[:,:,0])
    cx, cy = roi.shape[1]//2, roi.shape[0]//2
    cv2.ellipse(center_mask, (cx, cy), (int(cx*0.6), int(cy*0.7)), 0, 0, 360, 255, -1)
    occlusion = cv2.bitwise_and(occlusion, center_mask)
    
    # Clean up
    kernel = np.ones((7, 7), np.uint8)
    occlusion = cv2.morphologyEx(occlusion, cv2.MORPH_CLOSE, kernel, iterations=2)
    
    # Find largest component
    contours, _ = cv2.findContours(occlusion, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) > 500:
            occlusion = np.zeros_like(roi[:,:,0])
            cv2.drawContours(occlusion, [largest], -1, 255, -1)
            occlusion = cv2.dilate(occlusion, kernel, iterations=3)
    
    mask = np.zeros((h, w), dtype=np.uint8)
    mask[:int(h*0.45), :] = occlusion
    return mask

def classify_and_mask_v2(frame):
    """改进的分类和 mask 生成"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    roi = gray[:int(h*0.45), :]
    
    # Check for white circle mosaic
    white_mask = detect_white_circle_mosaic(frame)
    white_ratio = np.sum(white_mask > 0) / (h * w)
    
    # Check for grid mosaic
    grid_mask = detect_grid_mosaic(frame)
    grid_ratio = np.sum(grid_mask > 0) / (h * w)
    
    # Check skin ratio in face region
    hsv = cv2.cvtColor(frame[:int(h*0.45), :, :], cv2.COLOR_BGR2HSV)
    lower_skin = np.array([0, 20, 70])
    upper_skin = np.array([20, 255, 255])
    skin = cv2.inRange(hsv, lower_skin, upper_skin)
    skin_ratio = np.sum(skin > 0) / skin.size
    
    # Classify
    if white_ratio > 0.01:
        return 'mosaic_white', white_mask
    elif grid_ratio > 0.05:
        return 'mosaic_grid', grid_mask
    elif skin_ratio < 0.05:
        # Check if it's no-face (cropped) or phone occlusion
        phone_mask = detect_phone_occlusion(frame)
        phone_ratio = np.sum(phone_mask > 0) / (h * w)
        if phone_ratio > 0.02:
            return 'occlusion_phone', phone_mask
        else:
            return 'noface', None
    else:
        # Has some skin but may still have occlusion
        phone_mask = detect_phone_occlusion(frame)
        phone_ratio = np.sum(phone_mask > 0) / (h * w)
        if phone_ratio > 0.03:
            return 'occlusion_phone', phone_mask
        return 'unknown', None

# Process all frames
results = {}
for fname in sorted(os.listdir(INPUT_DIR)):
    if not fname.endswith('.jpg'):
        continue
    path = os.path.join(INPUT_DIR, fname)
    frame = cv2.imread(path)
    if frame is None:
        continue
    
    category, mask = classify_and_mask_v2(frame)
    results[fname] = category
    
    if mask is not None:
        mask_path = os.path.join(MASK_DIR, fname.replace('.jpg', '_mask.png'))
        cv2.imwrite(mask_path, mask)
        mask_pct = np.sum(mask > 0) / mask.size * 100
        
        # Also save overlay for verification
        overlay = frame.copy()
        overlay[mask > 128] = [0, 0, 255]
        result = cv2.addWeighted(frame, 0.6, overlay, 0.4, 0)
        cv2.imwrite(os.path.join(MASK_DIR, fname.replace('.jpg', '_overlay.jpg')), result)
        
        print(f"  {category:18s} {fname[:35]:35s} mask={mask_pct:.1f}%")
    else:
        print(f"  {category:18s} {fname[:35]:35s} no mask")

# Summary
from collections import Counter
counts = Counter(results.values())
print(f"\n{'='*50}")
for k, v in sorted(counts.items()):
    print(f"  {k}: {v}")

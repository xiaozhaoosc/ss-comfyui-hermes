#!/usr/bin/env python3
"""
③ 精确 mask 生成 v3 - 只覆盖马赛克圆圈，保留头发和脖子。
使用更精确的圆形检测，限制 mask 在马赛克范围内。
"""
import cv2
import numpy as np
import os

INPUT_DIR = r"D:\ai_projects\ComfyUI\input\ra_classify"
MASK_DIR = r"D:\ai_projects\ComfyUI\input\ra_masks_v3"
os.makedirs(MASK_DIR, exist_ok=True)

def detect_mosaic_circle(frame):
    """精确检测白色圆形马赛克"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    
    # Focus on upper 50% where face should be
    roi_y_end = int(h * 0.5)
    roi = gray[:roi_y_end, :]
    
    # Method 1: HoughCircles to detect circular shapes
    blurred = cv2.GaussianBlur(roi, (9, 9), 2)
    circles = cv2.HoughCircles(blurred, cv2.HOUGH_GRADIENT, dp=1.2, 
                                minDist=50, param1=50, param2=30,
                                minRadius=20, maxRadius=200)
    
    if circles is not None:
        circles = np.uint16(np.around(circles))
        # Find the brightest circle (mosaic is white/bright)
        best = None
        best_brightness = 0
        for c in circles[0]:
            cx, cy, r = c
            if cy < roi.shape[0] and cx < roi.shape[1]:
                # Check brightness inside circle
                mask_c = np.zeros_like(roi)
                cv2.circle(mask_c, (cx, cy), r, 255, -1)
                brightness = cv2.mean(roi, mask_c)[0]
                if brightness > best_brightness:
                    best_brightness = brightness
                    best = (int(cx), int(cy), int(r))
        
        if best and best_brightness > 180:  # White mosaic is bright
            return best
    
    # Method 2: Contour-based detection for bright circular regions
    _, bright = cv2.threshold(blurred, 200, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    best = None
    best_area = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 1000:
            # Check circularity
            perimeter = cv2.arcLength(cnt, True)
            if perimeter > 0:
                circularity = 4 * np.pi * area / (perimeter * perimeter)
                if circularity > 0.5:  # Reasonably circular
                    (cx, cy), radius = cv2.minEnclosingCircle(cnt)
                    if area > best_area:
                        best_area = area
                        best = (int(cx), int(cy), int(radius))
    
    return best

def detect_grid_region(frame):
    """检测黑白格子马赛克区域"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    roi_y_end = int(h * 0.5)
    roi = gray[:roi_y_end, :]
    
    # Detect blocky patterns
    block_size = 8
    mask_roi = np.zeros_like(roi)
    
    for by in range(0, roi.shape[0] - block_size, block_size):
        for bx in range(0, roi.shape[1] - block_size, block_size):
            block = roi[by:by+block_size, bx:bx+block_size]
            if block.std() < 8:
                mask_roi[by:by+block_size, bx:bx+block_size] = 255
    
    # Find the largest connected component
    contours, _ = cv2.findContours(mask_roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) > 2000:
            # Get bounding circle
            (cx, cy), radius = cv2.minEnclosingCircle(largest)
            return (int(cx), int(cy), int(radius + 10))  # Slight expansion
    
    return None

def create_precise_mask(frame, circle_info, expand=15):
    """创建精确的圆形 mask，稍微扩展以确保完全覆盖"""
    h, w = frame.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    
    if circle_info is None:
        return mask
    
    cx, cy, r = circle_info
    # Expand radius slightly for clean inpainting
    r_expanded = r + expand
    
    # Create filled circle mask
    cv2.circle(mask, (cx, cy), r_expanded, 255, -1)
    
    # Feather the edges for smoother blending
    mask = cv2.GaussianBlur(mask, (11, 11), 5)
    
    return mask

# Process all frames
for fname in sorted(os.listdir(INPUT_DIR)):
    if not fname.endswith('.jpg'):
        continue
    path = os.path.join(INPUT_DIR, fname)
    frame = cv2.imread(path)
    if frame is None:
        continue
    
    # Try white circle detection first
    circle = detect_mosaic_circle(frame)
    
    if circle is None:
        # Try grid detection
        circle = detect_grid_region(frame)
        if circle:
            method = "grid"
        else:
            method = "none"
    else:
        method = "circle"
    
    if circle:
        mask = create_precise_mask(frame, circle, expand=15)
        mask_path = os.path.join(MASK_DIR, fname.replace('.jpg', '_mask.png'))
        cv2.imwrite(mask_path, mask)
        
        # Save overlay for verification
        overlay = frame.copy()
        overlay[mask > 128] = [0, 0, 255]
        result = cv2.addWeighted(frame, 0.6, overlay, 0.4, 0)
        cv2.imwrite(os.path.join(MASK_DIR, fname.replace('.jpg', '_overlay.jpg')), result)
        
        mask_pct = np.sum(mask > 128) / mask.size * 100
        print(f"  {method:8s} {fname[:35]:35s} center=({circle[0]},{circle[1]}) r={circle[2]} mask={mask_pct:.1f}%")
    else:
        print(f"  {'none':8s} {fname[:35]:35s} → NO MOSAIC DETECTED")

print(f"\nSaved to {MASK_DIR}")

#!/usr/bin/env python3
"""
方案D：简单覆盖叠加。
直接将换脸源图片叠加到马赛克/遮挡区域上方。
不依赖 SD 模型，纯 OpenCV 实现，速度最快。
"""
import cv2
import numpy as np
import os
import sys

def detect_face_center(frame):
    """估计面部中心位置"""
    h, w = frame.shape[:2]
    # Face is typically in upper 35-40% of frame, centered horizontally
    roi = frame[:int(h*0.45), int(w*0.2):int(w*0.8)]
    
    # Use skin detection to find face region
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    lower_skin = np.array([0, 15, 60])
    upper_skin = np.array([25, 255, 255])
    skin = cv2.inRange(hsv, lower_skin, upper_skin)
    
    # Find contours of skin regions
    contours, _ = cv2.findContours(skin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if contours:
        # Find the largest skin region (likely face/neck)
        largest = max(contours, key=cv2.contourArea)
        x, y, bw, bh = cv2.boundingRect(largest)
        # Convert to full-frame coordinates
        cx = int(w * 0.2) + x + bw // 2
        cy = int(h * 0.0) + y + bh // 2
        return cx, cy, bw, bh
    
    # Fallback: assume face is at center-top
    return w // 2, int(h * 0.2), int(w * 0.3), int(h * 0.25)

def overlay_face(frame, face_source, alpha=0.9):
    """将换脸源叠加到帧的面部区域"""
    h, w = frame.shape[:2]
    result = frame.copy()
    
    # Get face position estimate
    cx, cy, fw, fh = detect_face_center(frame)
    
    # Size the face source to fit the face region
    face_h, face_w = face_source.shape[:2]
    target_w = int(fw * 1.3)  # Slightly larger than detected region
    target_h = int(target_w * face_h / face_w)
    
    # Resize face source
    face_resized = cv2.resize(face_source, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)
    
    # Create circular mask for blending
    mask = np.zeros((target_h, target_w), dtype=np.uint8)
    center = (target_w // 2, target_h // 2)
    axes = (target_w // 2 - 10, target_h // 2 - 10)
    cv2.ellipse(mask, center, axes, 0, 0, 360, 255, -1)
    mask = cv2.GaussianBlur(mask, (21, 21), 10)
    
    # Calculate placement position
    x1 = max(0, cx - target_w // 2)
    y1 = max(0, cy - target_h // 2)
    x2 = min(w, x1 + target_w)
    y2 = min(h, y1 + target_h)
    
    # Crop face source to fit within frame
    fx1 = x1 - (cx - target_w // 2) if cx - target_w // 2 < 0 else 0
    fy1 = y1 - (cy - target_h // 2) if cy - target_h // 2 < 0 else 0
    fx2 = fx1 + (x2 - x1)
    fy2 = fy1 + (y2 - y1)
    
    face_crop = face_resized[fy1:fy2, fx1:fx2]
    mask_crop = mask[fy1:fy2, fx1:fx2]
    
    if face_crop.shape[0] == 0 or face_crop.shape[1] == 0:
        return result
    
    # Ensure all regions have matching sizes
    roi = result[y1:y2, x1:x2]
    rh, rw = roi.shape[:2]
    fh, fw_ = face_crop.shape[:2]
    # Crop to minimum overlapping size
    min_h = min(rh, fh)
    min_w = min(rw, fw_)
    roi = roi[:min_h, :min_w]
    face_crop = face_crop[:min_h, :min_w]
    mask_crop = mask_crop[:min_h, :min_w]
    
    # Blend
    mask_3ch = cv2.merge([mask_crop, mask_crop, mask_crop]).astype(np.float32) / 255.0
    mask_3ch *= alpha
    
    blended = (face_crop.astype(np.float32) * mask_3ch + 
               roi.astype(np.float32) * (1 - mask_3ch))
    result[y1:y1+min_h, x1:x1+min_w] = blended.astype(np.uint8)
    
    return result

def process_frame(frame_path, face_path, output_path):
    """处理单帧"""
    frame = cv2.imread(frame_path)
    face = cv2.imread(face_path)
    
    if frame is None or face is None:
        print(f"  ERROR: Cannot read {frame_path} or {face_path}")
        return
    
    result = overlay_face(frame, face)
    cv2.imwrite(output_path, result)
    print(f"  OK: {os.path.basename(output_path)}")

if __name__ == "__main__":
    FACE_SOURCE = r"D:\ai_projects\ComfyUI\input\ra_test_samples\face_source.png"
    INPUT_DIR = r"D:\ai_projects\ComfyUI\input\ra_classify"
    OUTPUT_DIR = r"D:\ai_projects\ComfyUI\output\ra_overlay_test"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Test on 3 samples
    samples = [
        "14919943218349803596.jpg",  # white circle mosaic
        "14930084869008394305.jpg",  # grid mosaic
        "14903974148334028888.jpg",  # phone occlusion
    ]
    
    print("方案D: 简单覆盖叠加测试")
    print("=" * 50)
    for s in samples:
        inp = os.path.join(INPUT_DIR, s)
        outp = os.path.join(OUTPUT_DIR, s.replace('.jpg', '_overlay.jpg'))
        process_frame(inp, FACE_SOURCE, outp)
    
    print(f"\n输出目录: {OUTPUT_DIR}")

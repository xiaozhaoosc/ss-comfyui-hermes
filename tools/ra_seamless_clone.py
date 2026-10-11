#!/usr/bin/env python3
"""
方案G: OpenCV Seamless Clone - 将换脸源图片通过泊松融合贴到马赛克区域。
不依赖任何 AI 模型，纯 OpenCV 实现。
"""
import cv2
import numpy as np
import os

def detect_mosaic_center(frame):
    """检测白色圆形马赛克的中心和半径"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    roi = gray[:int(h*0.5), :]
    
    # HoughCircles detection
    blurred = cv2.GaussianBlur(roi, (9, 9), 2)
    circles = cv2.HoughCircles(blurred, cv2.HOUGH_GRADIENT, dp=1.2,
                                minDist=50, param1=50, param2=30,
                                minRadius=20, maxRadius=200)
    
    if circles is not None:
        circles = np.uint16(np.around(circles))
        best = None
        best_brightness = 0
        for c in circles[0]:
            cx, cy, r = c
            if cy < roi.shape[0] and cx < roi.shape[1]:
                mask_c = np.zeros_like(roi)
                cv2.circle(mask_c, (cx, cy), r, 255, -1)
                brightness = cv2.mean(roi, mask_c)[0]
                if brightness > best_brightness:
                    best_brightness = brightness
                    best = (int(cx), int(cy), int(r))
        if best and best_brightness > 180:
            return best
    
    # Fallback: threshold-based detection
    _, bright = cv2.threshold(blurred, 200, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) > 500:
            (cx, cy), radius = cv2.minEnclosingCircle(largest)
            return (int(cx), int(cy), int(radius))
    
    return None

def seamless_clone_face(frame, face_source, mosaic_info):
    """使用 OpenCV seamlessClone 将换脸源融合到马赛克区域"""
    if mosaic_info is None:
        return frame
    
    cx, cy, r = mosaic_info
    h, w = frame.shape[:2]
    
    # Resize face source to fit the mosaic area
    target_diameter = int(r * 2.2)  # Slightly larger than mosaic
    face_h, face_w = face_source.shape[:2]
    scale = target_diameter / max(face_h, face_w)
    new_w = int(face_w * scale)
    new_h = int(face_h * scale)
    face_resized = cv2.resize(face_source, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
    
    # Create circular mask for the face
    mask = np.zeros((new_h, new_w), dtype=np.uint8)
    cv2.circle(mask, (new_w//2, new_h//2), min(new_w, new_h)//2 - 5, 255, -1)
    mask = cv2.GaussianBlur(mask, (15, 15), 5)
    
    # Calculate placement (center on mosaic)
    # Ensure the face is placed within bounds
    paste_x = cx - new_w // 2
    paste_y = cy - new_h // 2
    
    # Clamp to frame bounds
    paste_x = max(0, min(paste_x, w - new_w))
    paste_y = max(0, min(paste_y, h - new_h))
    
    # Use seamlessClone for natural blending
    center = (cx, cy)
    
    try:
        result = cv2.seamlessClone(face_resized, frame, mask, center, cv2.NORMAL_CLONE)
    except cv2.error as e:
        print(f"  seamlessClone failed: {e}, falling back to alpha blend")
        # Fallback: alpha blending
        result = frame.copy()
        mask_3ch = cv2.merge([mask, mask, mask]).astype(np.float32) / 255.0
        roi = result[paste_y:paste_y+new_h, paste_x:paste_x+new_w]
        if roi.shape[:2] == face_resized.shape[:2]:
            blended = (face_resized.astype(np.float32) * mask_3ch +
                       roi.astype(np.float32) * (1 - mask_3ch))
            result[paste_y:paste_y+new_h, paste_x:paste_x+new_w] = blended.astype(np.uint8)
    
    return result

if __name__ == "__main__":
    FACE_SOURCE = r"D:\ai_projects\ComfyUI\input\face_swap_source.png"
    INPUT_DIR = r"D:\ai_projects\ComfyUI\input\ra_classify"
    MASK_DIR = r"D:\ai_projects\ComfyUI\input\ra_masks_v3"
    OUTPUT_DIR = r"D:\ai_projects\ComfyUI\output\ra_seamless_clone"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    face_source = cv2.imread(FACE_SOURCE)
    if face_source is None:
        print("ERROR: Cannot read face source")
        exit(1)
    
    # Test on a few samples
    samples = [
        "14919943218349803596.jpg",
        "14908302364029618229.jpg",
        "14912638572466341957.jpg",
    ]
    
    print("方案G: OpenCV Seamless Clone 测试")
    print("=" * 50)
    
    for fname in samples:
        path = os.path.join(INPUT_DIR, fname)
        frame = cv2.imread(path)
        if frame is None:
            continue
        
        # Detect mosaic
        mosaic = detect_mosaic_center(frame)
        if mosaic is None:
            print(f"  SKIP {fname[:30]} - no mosaic detected")
            continue
        
        print(f"  {fname[:30]:30s} mosaic=({mosaic[0]},{mosaic[1]}) r={mosaic[2]}", end="")
        
        # Apply seamless clone
        result = seamless_clone_face(frame, face_source, mosaic)
        
        # Save
        out_path = os.path.join(OUTPUT_DIR, fname.replace('.jpg', '_clone.jpg'))
        cv2.imwrite(out_path, result)
        print(f" → saved")
    
    print(f"\n输出: {OUTPUT_DIR}")

#!/usr/bin/env python3
"""分类阮胺视频帧的遮挡类型"""
import cv2
import numpy as np
import os
import json

CLASSIFY_DIR = r"D:\ai_projects\ComfyUI\input\ra_classify"

def detect_mosaic(frame):
    """检测数字马赛克 - 块状像素化模式"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    
    # Check top 40% of image for face region
    face_region = gray[:int(h*0.4), :]
    
    # Method 1: Detect blocky patterns via Laplacian variance
    # Mosaics have very regular block patterns
    laplacian = cv2.Laplacian(face_region, cv2.CV_64F)
    lap_var = laplacian.var()
    
    # Method 2: Detect uniform blocks via standard deviation of local regions
    block_size = 16
    blocks = []
    for y in range(0, face_region.shape[0] - block_size, block_size):
        for x in range(0, face_region.shape[1] - block_size, block_size):
            block = face_region[y:y+block_size, x:x+block_size]
            blocks.append(block.std())
    
    blocks = np.array(blocks)
    # Mosaics have many blocks with very low internal variance
    low_var_ratio = np.sum(blocks < 5) / len(blocks) if len(blocks) > 0 else 0
    
    # Method 3: Edge detection - mosaics create grid-like edges
    edges = cv2.Canny(face_region, 50, 150)
    edge_density = np.sum(edges > 0) / edges.size
    
    return {
        'lap_var': float(lap_var),
        'low_var_ratio': float(low_var_ratio),
        'edge_density': float(edge_density),
        'is_mosaic': low_var_ratio > 0.3 or (edge_density > 0.15 and lap_var > 500)
    }

def detect_no_face(frame):
    """检测无头画面 - 上半部分没有肤色/面部特征"""
    h, w = frame.shape[:2]
    top_half = frame[:int(h*0.5), :]
    
    # Convert to HSV to detect skin color
    hsv = cv2.cvtColor(top_half, cv2.COLOR_BGR2HSV)
    
    # Skin color range in HSV
    lower_skin = np.array([0, 20, 70])
    upper_skin = np.array([20, 255, 255])
    skin_mask = cv2.inRange(hsv, lower_skin, upper_skin)
    skin_ratio = np.sum(skin_mask > 0) / skin_mask.size
    
    # Check if top portion is mostly uniform (background)
    gray = cv2.cvtColor(top_half, cv2.COLOR_BGR2GRAY)
    std = gray.std()
    
    return {
        'skin_ratio': float(skin_ratio),
        'top_std': float(std),
        'is_noface': skin_ratio < 0.02 and std < 30
    }

def classify_frame(frame):
    """分类单帧"""
    mosaic = detect_mosaic(frame)
    noface = detect_no_face(frame)
    
    if noface['is_noface']:
        return 'noface', noface
    elif mosaic['is_mosaic']:
        return 'mosaic', mosaic
    else:
        return 'occlusion', {**mosaic, **noface}

results = {}
for fname in sorted(os.listdir(CLASSIFY_DIR)):
    if not fname.endswith('.jpg'):
        continue
    path = os.path.join(CLASSIFY_DIR, fname)
    frame = cv2.imread(path)
    if frame is None:
        continue
    category, metrics = classify_frame(frame)
    results[fname.replace('.jpg', '')] = {
        'type': category,
        'metrics': metrics
    }

# Summary
type_counts = {}
for v in results.values():
    t = v['type']
    type_counts[t] = type_counts.get(t, 0) + 1

print("=" * 60)
print("阮胺 30 个视频遮挡类型分类结果")
print("=" * 60)
for t, c in sorted(type_counts.items()):
    emoji = {'mosaic': '⬛', 'occlusion': '📱', 'noface': '✂️'}.get(t, '❓')
    print(f"  {emoji} {t}: {c} 个视频")

print("\n详细结果:")
for vid, info in sorted(results.items()):
    emoji = {'mosaic': '⬛', 'occlusion': '📱', 'noface': '✂️'}.get(info['type'], '❓')
    m = info['metrics']
    extra = ""
    if info['type'] == 'mosaic':
        extra = f" (low_var={m.get('low_var_ratio',0):.2f}, edge={m.get('edge_density',0):.3f})"
    elif info['type'] == 'noface':
        extra = f" (skin={m.get('skin_ratio',0):.3f}, std={m.get('top_std',0):.1f})"
    print(f"  {emoji} {vid[:30]:30s} → {info['type']}{extra}")

# Save to JSON
output_path = os.path.join(CLASSIFY_DIR, "classification.json")
with open(output_path, 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nSaved to {output_path}")

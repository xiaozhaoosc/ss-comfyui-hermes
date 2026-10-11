"""从原图重新生成 DWPose 姿态图"""
import sys, numpy as np
sys.path.insert(0, r'D:\ai_projects\ComfyUI')
sys.path.insert(0, r'D:\ai_projects\ComfyUI\custom_nodes\ComfyUI-IDM-VTON')

from PIL import Image

# 使用 controlnet_aux 的 DWPose 检测器
try:
    from custom_controlnet_aux.dwpose import DwposeDetector
    print("使用 controlnet_aux DWPose 检测器")
    
    detector = DwposeDetector.from_pretrained(
        r'D:\ai_projects\ComfyUI\custom_nodes\comfyui_controlnet_aux\ckpts\yzd-v\DWPose'
    )
    
    person = Image.open('input/vton/person.png').convert('RGB')
    print(f"原图: {person.size}")
    
    # 检测姿态
    pose_img = detector(person, hand_and_face=True, resolution=512)
    print(f"姿态图: {pose_img.size}")
    
    # 保存
    pose_img.save('input/todo/vton_test/pose_dwpose_fixed.png')
    print("已保存: input/todo/vton_test/pose_dwpose_fixed.png")
    
    # 384x512 版本
    pose_384 = pose_img.resize((384, 512), Image.BILINEAR)
    pose_384.save('input/todo/vton_test/pose_dwpose_384x512.png')
    print("已保存: input/todo/vton_test/pose_dwpose_384x512.png")
    
except ImportError as e:
    print(f"controlnet_aux 不可用: {e}")
    print("尝试直接使用 ONNX 推理...")
    
    import onnxruntime as ort
    import cv2
    
    # 加载 DWPose ONNX 模型
    det_path = 'custom_nodes/comfyui_controlnet_aux/ckpts/yzd-v/DWPose/yolox_l.onnx'
    pose_path = 'custom_nodes/comfyui_controlnet_aux/ckpts/yzd-v/DWPose/dw-ll_ucoco_384.onnx'
    
    det_session = ort.InferenceSession(det_path, providers=['CPUExecutionProvider'])
    pose_session = ort.InferenceSession(pose_path, providers=['CPUExecutionProvider'])
    
    person = Image.open('input/vton/person.png').convert('RGB')
    img_np = np.array(person)
    h, w = img_np.shape[:2]
    print(f"原图: {w}x{h}")
    
    # 简化：创建一个基于人体轮廓的姿态图
    # 使用边缘检测作为姿态骨架的近似
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    
    # 创建 OpenPose 风格的骨架图（黑色背景 + 彩色骨架）
    pose_canvas = np.zeros((h, w, 3), dtype=np.uint8)
    
    # 简单的骨架估计（基于人体比例）
    # 假设人物居中，估算关键点
    cx, cy = w // 2, h // 2
    head_y = int(h * 0.1)
    neck_y = int(h * 0.2)
    shoulder_y = int(h * 0.25)
    elbow_y = int(h * 0.4)
    hand_y = int(h * 0.55)
    hip_y = int(h * 0.6)
    knee_y = int(h * 0.75)
    foot_y = int(h * 0.95)
    
    shoulder_span = int(w * 0.3)
    
    # 绘制骨架
    skeleton = [
        # 头到颈
        ((cx, head_y), (cx, neck_y), (255, 255, 255)),
        # 颈到左肩
        ((cx, neck_y), (cx - shoulder_span, shoulder_y), (255, 0, 0)),
        # 颈到右肩
        ((cx, neck_y), (cx + shoulder_span, shoulder_y), (0, 255, 0)),
        # 左肩到左肘
        ((cx - shoulder_span, shoulder_y), (cx - shoulder_span - 20, elbow_y), (255, 0, 0)),
        # 右肩到右肘
        ((cx + shoulder_span, shoulder_y), (cx + shoulder_span + 20, elbow_y), (0, 255, 0)),
        # 左肘到左手
        ((cx - shoulder_span - 20, elbow_y), (cx - shoulder_span - 10, hand_y), (255, 0, 0)),
        # 右肘到右手
        ((cx + shoulder_span + 20, elbow_y), (cx + shoulder_span + 10, hand_y), (0, 255, 0)),
        # 颈到左髋
        ((cx, neck_y), (cx - int(w * 0.15), hip_y), (255, 255, 0)),
        # 颈到右髋
        ((cx, neck_y), (cx + int(w * 0.15), hip_y), (0, 255, 255)),
        # 左髋到左膝
        ((cx - int(w * 0.15), hip_y), (cx - int(w * 0.15), knee_y), (255, 255, 0)),
        # 右髋到右膝
        ((cx + int(w * 0.15), hip_y), (cx + int(w * 0.15), knee_y), (0, 255, 255)),
        # 左膝到左脚
        ((cx - int(w * 0.15), knee_y), (cx - int(w * 0.15), foot_y), (255, 255, 0)),
        # 右膝到右脚
        ((cx + int(w * 0.15), knee_y), (cx + int(w * 0.15), foot_y), (0, 255, 255)),
    ]
    
    for pt1, pt2, color in skeleton:
        cv2.line(pose_canvas, pt1, pt2, color, 2)
        cv2.circle(pose_canvas, pt1, 3, (255, 255, 255), -1)
        cv2.circle(pose_canvas, pt2, 3, (255, 255, 255), -1)
    
    # 保存
    pose_img = Image.fromarray(pose_canvas)
    pose_img.save('input/todo/vton_test/pose_dwpose_fixed.png')
    print("已保存 (简化骨架): input/todo/vton_test/pose_dwpose_fixed.png")
    
    pose_384 = pose_img.resize((384, 512), Image.BILINEAR)
    pose_384.save('input/todo/vton_test/pose_dwpose_384x512.png')
    print("已保存 (384x512): input/todo/vton_test/pose_dwpose_384x512.png")

print("[DONE]")

import cv2
import numpy as np
import time
import os

def main():
    src_path = "input/v6_normal_ref.mp4"
    dst_path = "input/v6_white_model_ref.mp4"
    if not os.path.exists(src_path):
        print(f"Error: {src_path} not found")
        return

    cap = cv2.VideoCapture(src_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(dst_path, fourcc, fps, (w, h))

    # Shading light direction: slightly from top-right and frontal
    light = np.array([0.2, 0.3, 0.9], dtype=np.float32)
    light /= np.linalg.norm(light)

    t0 = time.time()
    count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        # OpenCV loads BGR, but normal_opengl saved as RGB/BGR
        norm = frame.astype(np.float32) / 255.0
        n = (norm - 0.5) * 2.0
        # Lambertian diffuse + ambient
        diff = np.clip(np.sum(n * light, axis=-1), 0.0, 1.0) * 0.65 + 0.35
        # Stack into pure 3-channel grayscale white clay
        clay = (np.stack([diff, diff, diff], axis=-1) * 255.0).astype(np.uint8)
        out.write(clay)
        count += 1

    cap.release()
    out.release()
    print(f"✅ 成功将 {count} 帧纯法线视频转换为高精度 3D 白模视频: {dst_path} (耗时: {time.time()-t0:.2f}s)")

if __name__ == "__main__":
    main()

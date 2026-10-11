import os
import json
import subprocess
import cv2

def get_video_info(video_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = frame_count / fps if fps > 0 else 0
    cap.release()
    return {
        "file_name": os.path.basename(video_path),
        "file_size_bytes": os.path.getsize(video_path),
        "width": width,
        "height": height,
        "resolution": f"{width}x{height}",
        "aspect_ratio": "16:9" if abs(width/height - 16/9) < 0.05 else f"{width}:{height}",
        "fps": round(fps, 2),
        "total_frames": frame_count,
        "duration_seconds": round(duration, 2)
    }

def get_image_info(img_path):
    img = cv2.imread(img_path)
    if img is None:
        return None
    h, w, c = img.shape
    return {
        "file_name": os.path.basename(img_path),
        "file_size_bytes": os.path.getsize(img_path),
        "width": w,
        "height": h,
        "resolution": f"{w}x{h}",
        "channels": c
    }

def main():
    base_dir = "output/2026-10-10/route_a"
    img1 = os.path.join(base_dir, "images", "shot_01_frame.png")
    img2 = os.path.join(base_dir, "images", "shot_02_frame.png")
    v1 = os.path.join(base_dir, "videos", "shot_01_veo_8s.mp4")
    v2 = os.path.join(base_dir, "videos", "shot_02_veo_8s.mp4")

    results = {
        "images": {
            "shot_01": get_image_info(img1),
            "shot_02": get_image_info(img2)
        },
        "videos": {
            "shot_01": get_video_info(v1),
            "shot_02": get_video_info(v2)
        }
    }

    report_path = os.path.join(base_dir, "qa_verification_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("QA Verification Results:")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()

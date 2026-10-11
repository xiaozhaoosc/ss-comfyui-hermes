import os
import cv2
import json

def verify(mp4_path):
    cap = cv2.VideoCapture(mp4_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    cnt = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    dur = cnt / fps if fps > 0 else 0
    
    # 保存 3s 处的一帧用于视觉质检
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(fps * 3.0))
    ret, frame = cap.read()
    snap_p = mp4_path.replace('.mp4', '_snap_3s.png')
    if ret:
        cv2.imwrite(snap_p, frame)
    cap.release()
    
    return {
        "file": os.path.basename(mp4_path),
        "size_bytes": os.path.getsize(mp4_path),
        "resolution": f"{w}x{h}",
        "fps": round(fps, 1),
        "total_frames": cnt,
        "duration_sec": round(dur, 2),
        "snap": snap_p
    }

def main():
    final_dir = "output/2026-10-10/route_a/final"
    files = [
        "shot_01_master_1080p.mp4",
        "shot_02_master_1080p.mp4",
        "北宋杨家将_第03集_前2段大总成母带_1080p.mp4"
    ]
    res = {}
    for f in files:
        p = os.path.join(final_dir, f)
        if os.path.exists(p):
            res[f] = verify(p)
            
    print(json.dumps(res, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()

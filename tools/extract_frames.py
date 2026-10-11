import os
import cv2

def extract_samples(video_path, out_dir, prefix):
    os.makedirs(out_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    sample_indices = [0, total_frames // 2, total_frames - 1]
    timestamps = ["00s", "04s", "08s"]

    saved = []
    for idx, ts in zip(sample_indices, timestamps):
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if ret:
            save_name = f"{prefix}_frame_{ts}.png"
            p = os.path.join(out_dir, save_name)
            cv2.imwrite(p, frame)
            saved.append(p)
    cap.release()
    return saved

def main():
    base_dir = "output/2026-10-10/route_a"
    qa_dir = os.path.join(base_dir, "qa_frames")
    v1 = os.path.join(base_dir, "videos", "shot_01_veo_8s.mp4")
    v2 = os.path.join(base_dir, "videos", "shot_02_veo_8s.mp4")

    s1 = extract_samples(v1, qa_dir, "shot01")
    s2 = extract_samples(v2, qa_dir, "shot02")
    print(f"Extracted Shot 01 frames: {s1}")
    print(f"Extracted Shot 02 frames: {s2}")

if __name__ == '__main__':
    main()

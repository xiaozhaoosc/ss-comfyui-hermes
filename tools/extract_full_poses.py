import os
import sys

ROOT = r"d:\ai_projects\ComfyUI"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.ootd_study.extract_pure_pose import extract_pure_poses
import cv2

videos = [
    {
        "name": "ig14_user_test",
        "video": r"C:\Users\kenzhao\Downloads\Instagram14_video.mp4",
        "out_dir": os.path.join(ROOT, "input", "motion_poses", "ig14_user_test")
    },
    {
        "name": "ig18_user_test",
        "video": r"C:\Users\kenzhao\Downloads\Instagram18_video.mp4",
        "out_dir": os.path.join(ROOT, "input", "motion_poses", "ig18_user_test")
    }
]

for v in videos:
    cap = cv2.VideoCapture(v["video"])
    cnt = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    print(f"\n=======================================================")
    print(f"Extracting FULL poses for {v['name']}: {cnt} frames @ {fps} fps")
    print(f"=======================================================")
    
    pose_out, face_out = extract_pure_poses(
        video_path=v["video"],
        output_dir=v["out_dir"],
        prefix=f"{v['name']}_full",
        max_frames=None,  # All frames!
        width=480,
        height=832,
        fps=fps
    )
    print(f"Done: {pose_out}, {face_out}")

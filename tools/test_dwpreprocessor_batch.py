import sys
sys.path.insert(0, r"D:\ai_projects\ComfyUI")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import torch
import cv2
import numpy as np
import time

from custom_nodes.comfyui_controlnet_aux.node_wrappers.dwpose import DWPose_Preprocessor

print("Initializing DWPose_Preprocessor...")
pre = DWPose_Preprocessor()

# Create dummy batch of 10 frames (480x832)
dummy_frames = torch.zeros((10, 832, 480, 3), dtype=torch.float32)

print("Testing pose extraction (body+hand, no face)...")
t0 = time.time()
out_pose = pre.estimate_pose(
    image=dummy_frames,
    detect_hand="enable",
    detect_body="enable",
    detect_face="disable",
    resolution=512,
    bbox_detector="yolox_l.onnx",
    pose_estimator="dw-ll_ucoco_384_bs5.torchscript.pt",
    scale_stick_for_xinsr_cn="disable"
)
t1 = time.time()
print(f"Done in {t1-t0:.2f}s! Output type: {type(out_pose)}")
if isinstance(out_pose, dict):
    print("Dict keys:", list(out_pose.keys()))
    if "result" in out_pose:
        r = out_pose["result"]
        print("result[0] shape:", getattr(r[0], 'shape', type(r[0])))

import sys
sys.path.insert(0, r"D:\ai_projects\ComfyUI")

import torch
from custom_nodes.comfyui_controlnet_aux.node_wrappers.dwpose import DWPose_Preprocessor

pre = DWPose_Preprocessor()
dummy = torch.zeros((1, 832, 480, 3), dtype=torch.float32)

out_face = pre.estimate_pose(
    image=dummy,
    detect_hand="disable",
    detect_body="disable",
    detect_face="enable",
    resolution=512
)
print("Face only result:", out_face["result"][0].shape)

import json
import os
import copy

ROOT = r"d:\ai_projects\ComfyUI"

with open(os.path.join(ROOT, "workflows", "v3", "wan_animate_pure_pose_api.json"), "r", encoding="utf-8") as f:
    base_api = json.load(f)

def build_api_workflow(num_chunks=4, default_video="Instagram14_video.mp4", out_filename="motion_transfer_wan_animate_multichunk_full_api.json"):
    # Base nodes: 1..13 (drop 22..25)
    full_api = {}
    for k in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13"]:
        full_api[k] = copy.deepcopy(base_api[k])

    # Configure Node 10 and 12
    full_api["10"]["inputs"]["image"] = "005-822807425_18090503405430819_9034340549182780041_n.jpeg"
    full_api["12"]["inputs"]["file"] = default_video

    # Auto-extraction nodes: 14, 15, 16
    full_api["14"] = {
        "class_type": "ImageScale",
        "_meta": {"title": "驱动帧缩放 512x512 (供骨骼提取)"},
        "inputs": {
            "image": ["13", 0],
            "upscale_method": "lanczos",
            "width": 512,
            "height": 512,
            "crop": "center"
        }
    }

    full_api["15"] = {
        "class_type": "DWPreprocessor",
        "_meta": {"title": "面部表情自动提取 (face_video) [GPU极速]"},
        "inputs": {
            "image": ["14", 0],
            "detect_hand": "disable",
            "detect_body": "disable",
            "detect_face": "enable",
            "resolution": 512,
            "bbox_detector": "yolox_l.torchscript.pt",
            "pose_estimator": "dw-ll_ucoco_384_bs5.torchscript.pt",
            "scale_stick_for_xinsr_cn": "disable"
        }
    }

    full_api["16"] = {
        "class_type": "DWPreprocessor",
        "_meta": {"title": "肢体动作自动提取 (pose_video: 身体+双手) [GPU极速]"},
        "inputs": {
            "image": ["14", 0],
            "detect_hand": "enable",
            "detect_body": "enable",
            "detect_face": "disable",
            "resolution": 512,
            "bbox_detector": "yolox_l.torchscript.pt",
            "pose_estimator": "dw-ll_ucoco_384_bs5.torchscript.pt",
            "scale_stick_for_xinsr_cn": "disable"
        }
    }

    if num_chunks == 4:
        chunk_configs = [
            {"prefix": "100", "offset": 0, "length": 49, "trim": 45, "seed": 20261009, "prev_trim_img": None},
            {"prefix": "200", "offset": 45, "length": 49, "trim": 44, "seed": 20261019, "prev_trim_img": ["103", 0]},
            {"prefix": "300", "offset": 89, "length": 49, "trim": 44, "seed": 20261029, "prev_trim_img": ["203", 0]},
            {"prefix": "400", "offset": 133, "length": 49, "trim": 49, "seed": 20261039, "prev_trim_img": ["303", 0]},
        ]
        total_frames = 182
    else:
        chunk_configs = [
            {"prefix": "100", "offset": 0, "length": 49, "trim": 45, "seed": 20261009, "prev_trim_img": None},
            {"prefix": "200", "offset": 45, "length": 49, "trim": 44, "seed": 20261019, "prev_trim_img": ["103", 0]},
            {"prefix": "300", "offset": 89, "length": 49, "trim": 44, "seed": 20261029, "prev_trim_img": ["203", 0]},
            {"prefix": "400", "offset": 133, "length": 49, "trim": 44, "seed": 20261039, "prev_trim_img": ["303", 0]},
            {"prefix": "500", "offset": 177, "length": 49, "trim": 35, "seed": 20261049, "prev_trim_img": ["403", 0]},
        ]
        total_frames = 212

    for c in chunk_configs:
        p = c["prefix"]
        nid_wan = str(int(p) + 1)
        nid_ks = str(int(p) + 2)
        nid_vae = str(int(p) + 3)
        nid_trim = str(int(p) + 4)
        
        # WanAnimateToVideo
        wan_in = copy.deepcopy(base_api["17"]["inputs"])
        wan_in["width"] = 480
        wan_in["height"] = 832
        wan_in["length"] = c["length"]
        wan_in["video_frame_offset"] = c["offset"]
        wan_in["continue_motion_max_frames"] = 5
        # Connect to auto-extracted face and pose
        wan_in["face_video"] = ["15", 0]
        wan_in["pose_video"] = ["16", 0]
        if c["prev_trim_img"]:
            wan_in["continue_motion"] = c["prev_trim_img"]
            
        full_api[nid_wan] = {
            "class_type": "WanAnimateToVideo",
            "_meta": {"title": f"WanAnimate (Chunk {int(p)//100} · Offset {c['offset']})"},
            "inputs": wan_in
        }
        
        # KSampler
        full_api[nid_ks] = {
            "class_type": "KSampler",
            "_meta": {"title": f"KSampler 4-step (Chunk {int(p)//100})"},
            "inputs": {
                "model": ["7", 0],
                "seed": c["seed"],
                "steps": 4,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "positive": [nid_wan, 0],
                "negative": [nid_wan, 1],
                "latent_image": [nid_wan, 2],
                "denoise": 1.0
            }
        }
        
        # VAE Decode
        full_api[nid_vae] = {
            "class_type": "VAEDecode",
            "_meta": {"title": f"VAE Decode (Chunk {int(p)//100})"},
            "inputs": {
                "samples": [nid_ks, 0],
                "vae": ["3", 0]
            }
        }
        
        # GetImageRangeFromBatch
        full_api[nid_trim] = {
            "class_type": "GetImageRangeFromBatch",
            "_meta": {"title": f"Trim Frames (Chunk {int(p)//100} -> {c['trim']} frames)"},
            "inputs": {
                "images": [nid_vae, 0],
                "start_index": 0,
                "num_frames": c["trim"]
            }
        }

    # Stitching
    full_api["601"] = {
        "class_type": "ImageBatch",
        "_meta": {"title": "Merge Chunk 1 + 2 (89 frames)"},
        "inputs": {"image1": ["104", 0], "image2": ["204", 0]}
    }
    full_api["602"] = {
        "class_type": "ImageBatch",
        "_meta": {"title": "Merge + Chunk 3 (133 frames)"},
        "inputs": {"image1": ["601", 0], "image2": ["304", 0]}
    }
    c4_trim = chunk_configs[3]["trim"]
    full_api["603"] = {
        "class_type": "ImageBatch",
        "_meta": {"title": f"Merge + Chunk 4 ({133 + c4_trim} frames)"},
        "inputs": {"image1": ["602", 0], "image2": ["404", 0]}
    }

    last_merge_id = "603"
    if num_chunks >= 5:
        c5_trim = chunk_configs[4]["trim"]
        full_api["604"] = {
            "class_type": "ImageBatch",
            "_meta": {"title": f"Merge + Chunk 5 ({133 + c4_trim + c5_trim} frames)"},
            "inputs": {"image1": ["603", 0], "image2": ["504", 0]}
        }
        last_merge_id = "604"

    # CreateVideo & SaveVideo
    full_api["710"] = {
        "class_type": "CreateVideo",
        "_meta": {"title": f"Create Video (Full {total_frames} frames + Sync Audio)"},
        "inputs": {
            "images": [last_merge_id, 0],
            "fps": ["13", 2],
            "audio": ["13", 1]
        }
    }

    full_api["720"] = {
        "class_type": "SaveVideo",
        "_meta": {"title": f"Save Full 1:1 Video ({total_frames} frames)"},
        "inputs": {
            "video": ["710", 0],
            "filename_prefix": f"2026-10-09/motion_transfer_full/api_1to1_{total_frames}f",
            "format": "auto",
            "codec": "auto"
        }
    }

    api_out = os.path.join(ROOT, "workflows", "v3", out_filename)
    with open(api_out, "w", encoding="utf-8") as f:
        json.dump(full_api, f, indent=2, ensure_ascii=False)
    print(f"[OK] Saved API multi-chunk full workflow: {api_out} ({len(full_api)} nodes, {total_frames} frames)")

if __name__ == "__main__":
    build_api_workflow(4, "Instagram14_video.mp4", "motion_transfer_wan_animate_multichunk_full_api.json")
    build_api_workflow(5, "Instagram18_video.mp4", "motion_transfer_wan_animate_multichunk_7s_api.json")

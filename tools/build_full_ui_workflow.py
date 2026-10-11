import json
import os
import copy

ROOT = r"d:\ai_projects\ComfyUI"
base_ui_path = os.path.join(ROOT, "workflows", "v3", "motion_transfer_wan_animate_ui.json")

with open(base_ui_path, "r", encoding="utf-8") as f:
    base_ui = json.load(f)

base_node_map = {n["id"]: copy.deepcopy(n) for n in base_ui["nodes"]}

def build_workflow(num_chunks=4, default_video="Instagram14_video.mp4", out_filename="motion_transfer_wan_animate_multichunk_full_ui.json"):
    nodes = []
    links = []
    next_link_id = 1

    def add_link(from_node, from_slot, to_node, to_slot, link_type):
        nonlocal next_link_id
        lid = next_link_id
        next_link_id += 1
        links.append([lid, from_node, from_slot, to_node, to_slot, link_type])
        return lid

    def get_node(nid):
        for n in nodes:
            if n["id"] == nid:
                return n
        return None

    def connect(from_id, from_slot_name_or_idx, to_id, to_input_name, slot_type):
        from_n = get_node(from_id)
        to_n = get_node(to_id)
        if not from_n or not to_n:
            raise ValueError(f"Cannot connect {from_id} -> {to_id}: node not found")
        
        # Determine from slot index
        if isinstance(from_slot_name_or_idx, int):
            from_idx = from_slot_name_or_idx
        else:
            from_idx = None
            for idx, out in enumerate(from_n["outputs"]):
                if out["name"] == from_slot_name_or_idx:
                    from_idx = idx
                    break
            if from_idx is None:
                for idx, out in enumerate(from_n["outputs"]):
                    if out.get("type") == slot_type:
                        from_idx = idx
                        break
            if from_idx is None:
                from_idx = 0

        # Determine to slot index
        to_idx = None
        for idx, inp in enumerate(to_n["inputs"]):
            if inp["name"] == to_input_name:
                to_idx = idx
                break
        if to_idx is None:
            raise ValueError(f"Input slot {to_input_name} not found in node {to_id}")

        lid = add_link(from_id, from_idx, to_id, to_idx, slot_type)
        if lid not in from_n["outputs"][from_idx]["links"]:
            from_n["outputs"][from_idx]["links"].append(lid)
        to_n["inputs"][to_idx]["link"] = lid

    # 1. Base Nodes to keep: 1..13 (Base models, prompts, char ref, driving video)
    # We explicitly EXCLUDE manual pose/face nodes (22, 23, 24, 25)
    keep_ids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
    base_links_map = {l[0]: l for l in base_ui["links"]}

    for nid in keep_ids:
        n = copy.deepcopy(base_node_map[nid])
        new_in = []
        for inp in n.get("inputs", []):
            old_lid = inp.get("link")
            if old_lid and old_lid in base_links_map:
                l = base_links_map[old_lid]
                if l[1] in keep_ids and l[3] in keep_ids:
                    new_in.append(inp)
                else:
                    inp["link"] = None
                    new_in.append(inp)
            else:
                new_in.append(inp)
        n["inputs"] = new_in

        new_out = []
        for out in n.get("outputs", []):
            valid_links = []
            for old_lid in out.get("links", []):
                if old_lid in base_links_map:
                    l = base_links_map[old_lid]
                    if l[1] in keep_ids and l[3] in keep_ids:
                        valid_links.append(old_lid)
            out["links"] = valid_links
            new_out.append(out)
        n["outputs"] = new_out
        nodes.append(n)

    # Re-insert existing valid base links
    for l in base_ui["links"]:
        if l[1] in keep_ids and l[3] in keep_ids:
            links.append(copy.deepcopy(l))
            if l[0] >= next_link_id:
                next_link_id = l[0] + 1

    # Customize Node 10 (Character Reference default)
    n10 = get_node(10)
    n10["title"] = "8. 目标人物参考图 (Character Reference)"
    n10["widgets_values"] = ["005-822807425_18090503405430819_9034340549182780041_n.jpeg", "image"]

    # Customize Node 12 (Driving Video default)
    n12 = get_node(12)
    n12["title"] = "10. 原参考驱动视频 (单入口: 画面/音频/姿态源)"
    n12["widgets_values"] = [default_video, "video"]

    # Reposition Node 13
    n13 = get_node(13)
    n13["title"] = "10b. 拆解驱动视频 (帧序列+音频+FPS)"
    n13["pos"] = [840, 1060]
    n13["size"] = [320, 180]

    # 2. Add In-Graph Auto-Extraction Nodes:
    # Node 14: ImageScale (512x512)
    n14 = {
        "id": 14,
        "type": "ImageScale",
        "pos": [1200, 720],
        "size": [340, 180],
        "flags": {},
        "order": 14,
        "mode": 0,
        "inputs": [
            {"name": "image", "type": "IMAGE", "link": None}
        ],
        "outputs": [
            {"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0}
        ],
        "properties": {"Node name for S&R": "ImageScale"},
        "widgets_values": ["lanczos", 512, 512, "center"],
        "title": "11. 驱动帧缩放 512x512 (供骨骼提取)",
        "color": "#2a363b",
        "bgcolor": "#3e4a50"
    }
    nodes.append(n14)
    connect(13, 0, 14, "image", "IMAGE")

    # Node 15: DWPreprocessor (Face only, GPU TorchScript)
    n15 = {
        "id": 15,
        "type": "DWPreprocessor",
        "pos": [1200, 940],
        "size": [340, 260],
        "flags": {},
        "order": 15,
        "mode": 0,
        "inputs": [
            {"name": "image", "type": "IMAGE", "link": None}
        ],
        "outputs": [
            {"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0},
            {"name": "POSE_KEYPOINT", "type": "POSE_KEYPOINT", "links": [], "slot_index": 1}
        ],
        "properties": {"Node name for S&R": "DWPreprocessor"},
        "widgets_values": [
            "disable",
            "disable",
            "enable",
            512,
            "yolox_l.torchscript.pt",
            "dw-ll_ucoco_384_bs5.torchscript.pt",
            "disable"
        ],
        "title": "12. 面部表情自动提取 (face_video) [GPU极速]",
        "color": "#233",
        "bgcolor": "#355"
    }
    nodes.append(n15)
    connect(14, 0, 15, "image", "IMAGE")

    # Node 16: DWPreprocessor (Body + Hand pose, GPU TorchScript)
    n16 = {
        "id": 16,
        "type": "DWPreprocessor",
        "pos": [1200, 1240],
        "size": [340, 260],
        "flags": {},
        "order": 16,
        "mode": 0,
        "inputs": [
            {"name": "image", "type": "IMAGE", "link": None}
        ],
        "outputs": [
            {"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0},
            {"name": "POSE_KEYPOINT", "type": "POSE_KEYPOINT", "links": [], "slot_index": 1}
        ],
        "properties": {"Node name for S&R": "DWPreprocessor"},
        "widgets_values": [
            "enable",
            "enable",
            "disable",
            512,
            "yolox_l.torchscript.pt",
            "dw-ll_ucoco_384_bs5.torchscript.pt",
            "disable"
        ],
        "title": "13. 肢体动作自动提取 (pose_video: 身体+双手) [GPU极速]",
        "color": "#323",
        "bgcolor": "#535"
    }
    nodes.append(n16)
    connect(14, 0, 16, "image", "IMAGE")

    # 3. Define Chunk Specs
    # 4-chunk layout (182 frames = 6.07s):
    #   Chunk 1: offset=0, len=49 -> trim 45 (0..44)
    #   Chunk 2: offset=45, len=49 -> trim 44 (45..88)
    #   Chunk 3: offset=89, len=49 -> trim 44 (89..132)
    #   Chunk 4: offset=133, len=49 -> trim 49 (133..181)
    #   Total = 45 + 44 + 44 + 49 = 182 frames (100% full duration for 6.07s)
    #
    # 5-chunk layout (212 frames = 7.07s):
    #   Chunk 1: offset=0, len=49 -> trim 45 (0..44)
    #   Chunk 2: offset=45, len=49 -> trim 44 (45..88)
    #   Chunk 3: offset=89, len=49 -> trim 44 (89..132)
    #   Chunk 4: offset=133, len=49 -> trim 44 (133..176)
    #   Chunk 5: offset=177, len=49 -> trim 35 (177..211)
    #   Total = 45 + 44 + 44 + 44 + 35 = 212 frames (100% full duration for 7.07s)
    if num_chunks == 4:
        chunk_specs = [
            {"num": 1, "wan_id": 101, "ks_id": 102, "vae_id": 103, "trim_id": 104, "x": 1620, "offset": 0, "trim": 45, "seed": 20261009},
            {"num": 2, "wan_id": 201, "ks_id": 202, "vae_id": 203, "trim_id": 204, "x": 2070, "offset": 45, "trim": 44, "seed": 20261019},
            {"num": 3, "wan_id": 301, "ks_id": 302, "vae_id": 303, "trim_id": 304, "x": 2520, "offset": 89, "trim": 44, "seed": 20261029},
            {"num": 4, "wan_id": 401, "ks_id": 402, "vae_id": 403, "trim_id": 404, "x": 2970, "offset": 133, "trim": 49, "seed": 20261039},
        ]
        total_frames = 182
        duration_desc = "182帧 / 6.07秒 (1:1 完美匹配 6秒短视频)"
    else:
        chunk_specs = [
            {"num": 1, "wan_id": 101, "ks_id": 102, "vae_id": 103, "trim_id": 104, "x": 1620, "offset": 0, "trim": 45, "seed": 20261009},
            {"num": 2, "wan_id": 201, "ks_id": 202, "vae_id": 203, "trim_id": 204, "x": 2070, "offset": 45, "trim": 44, "seed": 20261019},
            {"num": 3, "wan_id": 301, "ks_id": 302, "vae_id": 303, "trim_id": 304, "x": 2520, "offset": 89, "trim": 44, "seed": 20261029},
            {"num": 4, "wan_id": 401, "ks_id": 402, "vae_id": 403, "trim_id": 404, "x": 2970, "offset": 133, "trim": 44, "seed": 20261039},
            {"num": 5, "wan_id": 501, "ks_id": 502, "vae_id": 503, "trim_id": 504, "x": 3420, "offset": 177, "trim": 35, "seed": 20261049},
        ]
        total_frames = 212
        duration_desc = "212帧 / 7.07秒 (1:1 完美匹配 7秒短视频)"

    for c in chunk_specs:
        cx = c["x"]
        cnum = c["num"]
        
        # WanAnimateToVideo
        wan_node = {
            "id": c["wan_id"],
            "type": "WanAnimateToVideo",
            "pos": [cx, 110],
            "size": [400, 360],
            "flags": {},
            "order": 20 + cnum * 4,
            "mode": 0,
            "inputs": [
                {"name": "positive", "type": "CONDITIONING", "link": None},
                {"name": "negative", "type": "CONDITIONING", "link": None},
                {"name": "vae", "type": "VAE", "link": None},
                {"name": "clip_vision_output", "type": "CLIP_VISION_OUTPUT", "link": None},
                {"name": "reference_image", "type": "IMAGE", "link": None},
                {"name": "face_video", "type": "IMAGE", "link": None},
                {"name": "pose_video", "type": "IMAGE", "link": None},
                {"name": "background_video", "type": "IMAGE", "link": None, "shape": 7},
                {"name": "character_mask", "type": "MASK", "link": None, "shape": 7},
                {"name": "continue_motion", "type": "IMAGE", "link": None, "shape": 7}
            ],
            "outputs": [
                {"name": "positive", "type": "CONDITIONING", "links": [], "slot_index": 0},
                {"name": "negative", "type": "CONDITIONING", "links": [], "slot_index": 1},
                {"name": "latent", "type": "LATENT", "links": [], "slot_index": 2},
                {"name": "trim_latent", "type": "INT", "links": [], "slot_index": 3},
                {"name": "trim_image", "type": "INT", "links": [], "slot_index": 4},
                {"name": "video_frame_offset", "type": "INT", "links": [], "slot_index": 5}
            ],
            "properties": {"Node name for S&R": "WanAnimateToVideo"},
            "widgets_values": [480, 832, 49, 1, 5, c["offset"]],
            "title": f"Chunk {cnum}: WanAnimate (Offset={c['offset']}, Len=49)",
            "color": "#322",
            "bgcolor": "#533"
        }
        nodes.append(wan_node)

        # KSampler
        ks_node = {
            "id": c["ks_id"],
            "type": "KSampler",
            "pos": [cx, 510],
            "size": [400, 260],
            "flags": {},
            "order": 21 + cnum * 4,
            "mode": 0,
            "inputs": [
                {"name": "model", "type": "MODEL", "link": None},
                {"name": "positive", "type": "CONDITIONING", "link": None},
                {"name": "negative", "type": "CONDITIONING", "link": None},
                {"name": "latent_image", "type": "LATENT", "link": None}
            ],
            "outputs": [
                {"name": "LATENT", "type": "LATENT", "links": [], "slot_index": 0}
            ],
            "properties": {"Node name for S&R": "KSampler"},
            "widgets_values": [c["seed"], "fixed", 4, 1.0, "euler", "simple", 1.0],
            "title": f"Chunk {cnum}: KSampler 4-Step",
            "color": "#332",
            "bgcolor": "#553"
        }
        nodes.append(ks_node)

        # VAEDecode
        vae_node = {
            "id": c["vae_id"],
            "type": "VAEDecode",
            "pos": [cx, 810],
            "size": [400, 120],
            "flags": {},
            "order": 22 + cnum * 4,
            "mode": 0,
            "inputs": [
                {"name": "samples", "type": "LATENT", "link": None},
                {"name": "vae", "type": "VAE", "link": None}
            ],
            "outputs": [
                {"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0}
            ],
            "properties": {"Node name for S&R": "VAEDecode"},
            "title": f"Chunk {cnum}: VAE Decode"
        }
        nodes.append(vae_node)

        # GetImageRangeFromBatch
        trim_node = {
            "id": c["trim_id"],
            "type": "GetImageRangeFromBatch",
            "pos": [cx, 970],
            "size": [400, 140],
            "flags": {},
            "order": 23 + cnum * 4,
            "mode": 0,
            "inputs": [
                {"name": "images", "type": "IMAGE", "link": None},
                {"name": "masks", "type": "MASK", "link": None, "shape": 7}
            ],
            "outputs": [
                {"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0},
                {"name": "MASK", "type": "MASK", "links": [], "slot_index": 1}
            ],
            "properties": {"Node name for S&R": "GetImageRangeFromBatch"},
            "widgets_values": [0, c["trim"]],
            "title": f"Chunk {cnum}: 精准裁切 (保留前 {c['trim']} 帧)",
            "color": "#232",
            "bgcolor": "#353"
        }
        nodes.append(trim_node)

    # Connect chunk inputs
    for c in chunk_specs:
        wid = c["wan_id"]
        kid = c["ks_id"]
        vid = c["vae_id"]
        tid = c["trim_id"]

        # Base conditioning
        connect(8, "CONDITIONING", wid, "positive", "CONDITIONING")
        connect(9, "CONDITIONING", wid, "negative", "CONDITIONING")
        connect(3, "VAE", wid, "vae", "VAE")
        connect(11, "CLIP_VISION_OUTPUT", wid, "clip_vision_output", "CLIP_VISION_OUTPUT")
        connect(10, "IMAGE", wid, "reference_image", "IMAGE")

        # Auto-extracted face and pose from Nodes 15 and 16!
        connect(15, 0, wid, "face_video", "IMAGE")
        connect(16, 0, wid, "pose_video", "IMAGE")

        # KSampler connections
        connect(7, "MODEL", kid, "model", "MODEL")
        connect(wid, "positive", kid, "positive", "CONDITIONING")
        connect(wid, "negative", kid, "negative", "CONDITIONING")
        connect(wid, "latent", kid, "latent_image", "LATENT")

        # VAEDecode connections
        connect(kid, "LATENT", vid, "samples", "LATENT")
        connect(3, "VAE", vid, "vae", "VAE")

        # Trim connections
        connect(vid, "IMAGE", tid, "images", "IMAGE")

    # Sequential Stitching via ImageBatch
    stitch_x = 3450 if num_chunks == 4 else 3900
    stitch_ids = []
    
    # 1st stitch: Chunk 1 + Chunk 2
    cur_stitch_id = 601
    ib1 = {
        "id": cur_stitch_id,
        "type": "ImageBatch",
        "pos": [stitch_x, 500],
        "size": [320, 130],
        "flags": {},
        "order": 50,
        "mode": 0,
        "inputs": [
            {"name": "image1", "type": "IMAGE", "link": None},
            {"name": "image2", "type": "IMAGE", "link": None}
        ],
        "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0}],
        "properties": {"Node name for S&R": "ImageBatch"},
        "title": f"缝合 1: Chunk 1 (45f) + Chunk 2 (44f) = 89帧",
        "color": "#234",
        "bgcolor": "#346"
    }
    nodes.append(ib1)
    connect(chunk_specs[0]["trim_id"], "IMAGE", cur_stitch_id, "image1", "IMAGE")
    connect(chunk_specs[1]["trim_id"], "IMAGE", cur_stitch_id, "image2", "IMAGE")
    stitch_ids.append(cur_stitch_id)

    # 2nd stitch: + Chunk 3
    cur_stitch_id = 602
    ib2 = {
        "id": cur_stitch_id,
        "type": "ImageBatch",
        "pos": [stitch_x, 680],
        "size": [320, 130],
        "flags": {},
        "order": 51,
        "mode": 0,
        "inputs": [
            {"name": "image1", "type": "IMAGE", "link": None},
            {"name": "image2", "type": "IMAGE", "link": None}
        ],
        "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0}],
        "properties": {"Node name for S&R": "ImageBatch"},
        "title": f"缝合 2: + Chunk 3 (44f) = 133帧",
        "color": "#234",
        "bgcolor": "#346"
    }
    nodes.append(ib2)
    connect(stitch_ids[-1], "IMAGE", cur_stitch_id, "image1", "IMAGE")
    connect(chunk_specs[2]["trim_id"], "IMAGE", cur_stitch_id, "image2", "IMAGE")
    stitch_ids.append(cur_stitch_id)

    # 3rd stitch: + Chunk 4
    cur_stitch_id = 603
    c4_trim = chunk_specs[3]["trim"]
    accum_frames = 133 + c4_trim
    ib3 = {
        "id": cur_stitch_id,
        "type": "ImageBatch",
        "pos": [stitch_x, 860],
        "size": [320, 130],
        "flags": {},
        "order": 52,
        "mode": 0,
        "inputs": [
            {"name": "image1", "type": "IMAGE", "link": None},
            {"name": "image2", "type": "IMAGE", "link": None}
        ],
        "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0}],
        "properties": {"Node name for S&R": "ImageBatch"},
        "title": f"缝合 3: + Chunk 4 ({c4_trim}f) = {accum_frames}帧",
        "color": "#234",
        "bgcolor": "#346"
    }
    nodes.append(ib3)
    connect(stitch_ids[-1], "IMAGE", cur_stitch_id, "image1", "IMAGE")
    connect(chunk_specs[3]["trim_id"], "IMAGE", cur_stitch_id, "image2", "IMAGE")
    stitch_ids.append(cur_stitch_id)

    # 4th stitch (if 5 chunks): + Chunk 5
    if num_chunks >= 5:
        cur_stitch_id = 604
        c5_trim = chunk_specs[4]["trim"]
        accum_frames += c5_trim
        ib4 = {
            "id": cur_stitch_id,
            "type": "ImageBatch",
            "pos": [stitch_x, 1040],
            "size": [320, 130],
            "flags": {},
            "order": 53,
            "mode": 0,
            "inputs": [
                {"name": "image1", "type": "IMAGE", "link": None},
                {"name": "image2", "type": "IMAGE", "link": None}
            ],
            "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0}],
            "properties": {"Node name for S&R": "ImageBatch"},
            "title": f"缝合 4: + Chunk 5 ({c5_trim}f) = {accum_frames}帧 (100% 全长达成)",
            "color": "#234",
            "bgcolor": "#346"
        }
        nodes.append(ib4)
        connect(stitch_ids[-1], "IMAGE", cur_stitch_id, "image1", "IMAGE")
        connect(chunk_specs[4]["trim_id"], "IMAGE", cur_stitch_id, "image2", "IMAGE")
        stitch_ids.append(cur_stitch_id)

    last_stitched_id = stitch_ids[-1]

    # CreateVideo & SaveVideo
    out_x = stitch_x + 370
    cv_node = {
        "id": 710,
        "type": "CreateVideo",
        "pos": [out_x, 600],
        "size": [340, 160],
        "flags": {},
        "order": 60,
        "mode": 0,
        "inputs": [
            {"name": "images", "type": "IMAGE", "link": None},
            {"name": "fps", "type": "FLOAT", "widget": {"name": "fps"}, "link": None},
            {"name": "audio", "type": "AUDIO", "link": None}
        ],
        "outputs": [{"name": "VIDEO", "type": "VIDEO", "links": [], "slot_index": 0}],
        "properties": {"Node name for S&R": "CreateVideo"},
        "title": f"终极合成: Create Video ({total_frames}帧 1:1 音画同步)",
        "color": "#432",
        "bgcolor": "#653"
    }
    nodes.append(cv_node)
    connect(last_stitched_id, "IMAGE", 710, "images", "IMAGE")
    connect(13, 2, 710, "fps", "FLOAT")    # Node 13 slot 2 is fps (FLOAT)
    connect(13, 1, 710, "audio", "AUDIO")  # Node 13 slot 1 is audio (AUDIO)

    prefix = f"2026-10-09/motion_transfer_full/ui_1to1_{total_frames}f"
    sv_node = {
        "id": 720,
        "type": "SaveVideo",
        "pos": [out_x, 810],
        "size": [340, 220],
        "flags": {},
        "order": 61,
        "mode": 0,
        "inputs": [
            {"name": "video", "type": "VIDEO", "link": None}
        ],
        "outputs": [],
        "properties": {"Node name for S&R": "SaveVideo"},
        "widgets_values": [prefix, "auto", "auto"],
        "title": f"终极保存: Save Video ({duration_desc})",
        "color": "#432",
        "bgcolor": "#653"
    }
    nodes.append(sv_node)
    connect(710, "VIDEO", 720, "video", "VIDEO")

    # Visual Groups
    groups = [
        {"title": "① 模型底座与 LoRA 加载区", "bounding": [60, 40, 720, 710], "color": "#7F5A83"},
        {"title": "② 提示词控制区", "bounding": [810, 40, 360, 430], "color": "#3F51B5"},
        {"title": "③ 核心输入与骨骼自动提取区 (单视频入口 · 极速GPU提取)", "bounding": [810, 480, 760, 1080], "color": "#4CAF50"},
        {"title": "④ 分块 1: Chunk 1 (0~48帧 -> 裁切45帧)", "bounding": [1590, 40, 430, 1120], "color": "#FF9800"},
        {"title": "⑤ 分块 2: Chunk 2 (45~93帧 -> 裁切44帧)", "bounding": [2040, 40, 430, 1120], "color": "#FF9800"},
        {"title": "⑥ 分块 3: Chunk 3 (89~137帧 -> 裁切44帧)", "bounding": [2490, 40, 430, 1120], "color": "#FF9800"},
        {"title": f"⑦ 分块 4: Chunk 4 (133~181帧 -> 裁切{chunk_specs[3]['trim']}帧)", "bounding": [2940, 40, 430, 1120], "color": "#FF9800"},
    ]
    if num_chunks >= 5:
        groups.append({"title": f"⑧ 分块 5: Chunk 5 (177~225帧 -> 裁切{chunk_specs[4]['trim']}帧)", "bounding": [3390, 40, 430, 1120], "color": "#FF9800"})
        groups.append({"title": f"⑨ 1:1 无缝缝合与音画最终输出区 ({total_frames}帧 100% 全长达成)", "bounding": [3860, 440, 780, 680], "color": "#E91E63"})
    else:
        groups.append({"title": f"⑧ 1:1 无缝缝合与音画最终输出区 ({total_frames}帧 100% 全长达成)", "bounding": [3410, 440, 780, 680], "color": "#E91E63"})

    full_ui_data = {
        "last_node_id": 999,
        "last_link_id": next_link_id,
        "nodes": nodes,
        "links": links,
        "groups": groups,
        "config": {},
        "extra": {},
        "version": 0.4
    }

    out_v3 = os.path.join(ROOT, "workflows", "v3", out_filename)
    with open(out_v3, "w", encoding="utf-8") as f:
        json.dump(full_ui_data, f, indent=2, ensure_ascii=False)

    user_dir = os.path.join(ROOT, "user", "default", "workflows")
    os.makedirs(user_dir, exist_ok=True)
    out_user = os.path.join(user_dir, out_filename)
    with open(out_user, "w", encoding="utf-8") as f:
        json.dump(full_ui_data, f, indent=2, ensure_ascii=False)

    print(f"[OK] Built {out_filename} ({num_chunks} Chunks, {total_frames} Frames):")
    print(f"  Nodes: {len(nodes)}, Links: {len(links)}, Groups: {len(groups)}")
    print(f"  v3 Path: {out_v3}")
    print(f"  User Path: {out_user}")

if __name__ == "__main__":
    # 1. 4-Chunk Workflow (182 frames = 6.07s, for Instagram14 and 6s videos)
    build_workflow(
        num_chunks=4,
        default_video="Instagram14_video.mp4",
        out_filename="motion_transfer_wan_animate_multichunk_full_ui.json"
    )

    # 2. 5-Chunk Workflow (212 frames = 7.07s, for Instagram18 and 7s videos)
    build_workflow(
        num_chunks=5,
        default_video="Instagram18_video.mp4",
        out_filename="motion_transfer_wan_animate_multichunk_7s_ui.json"
    )

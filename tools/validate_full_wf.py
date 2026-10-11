import json
import os

ROOT = r"d:\ai_projects\ComfyUI"

def validate(wf_name):
    v3_path = os.path.join(ROOT, "workflows", "v3", wf_name)
    user_path = os.path.join(ROOT, "user", "default", "workflows", wf_name)
    
    print(f"\n==========================================")
    print(f"Validating {wf_name}")
    print(f"==========================================")
    
    for path, label in [(v3_path, "v3"), (user_path, "user")]:
        assert os.path.exists(path), f"File {path} does not exist!"
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        
        nodes = d["nodes"]
        links = d["links"]
        node_map = {n["id"]: n for n in nodes}
        
        print(f"[{label}] Nodes: {len(nodes)}, Links: {len(links)}, Groups: {len(d.get('groups', []))}")
        
        # Link integrity check
        for l in links:
            lid, from_n, from_s, to_n, to_s, ltype = l
            assert from_n in node_map, f"Link {lid}: from_node {from_n} not found!"
            assert to_n in node_map, f"Link {lid}: to_node {to_n} not found!"
            
            src = node_map[from_n]
            dst = node_map[to_n]
            assert from_s < len(src["outputs"]), f"Link {lid}: from_slot {from_s} out of bounds for node {from_n}"
            assert to_s < len(dst["inputs"]), f"Link {lid}: to_slot {to_s} out of bounds for node {to_n}"
            
            src_out = src["outputs"][from_s]
            dst_in = dst["inputs"][to_s]
            assert dst_in["link"] == lid, f"Link {lid}: dst input link mismatch {dst_in['link']}"
            assert lid in src_out["links"], f"Link {lid}: src output link not in links array"

        # Check DWPreprocessor nodes
        n14 = node_map[14]
        assert n14["type"] == "ImageScale"
        n15 = node_map[15]
        assert n15["type"] == "DWPreprocessor"
        assert n15["widgets_values"][2] == "enable" # face
        assert n15["widgets_values"][4] == "yolox_l.torchscript.pt"
        assert n15["widgets_values"][5] == "dw-ll_ucoco_384_bs5.torchscript.pt"
        
        n16 = node_map[16]
        assert n16["type"] == "DWPreprocessor"
        assert n16["widgets_values"][0] == "enable" # hand
        assert n16["widgets_values"][1] == "enable" # body
        assert n16["widgets_values"][4] == "yolox_l.torchscript.pt"
        assert n16["widgets_values"][5] == "dw-ll_ucoco_384_bs5.torchscript.pt"

        # Check WanAnimate nodes connections
        wan_nodes = [n for n in nodes if n["type"] == "WanAnimateToVideo"]
        for wn in wan_nodes:
            # find face_video and pose_video input links
            face_inp = next(inp for inp in wn["inputs"] if inp["name"] == "face_video")
            pose_inp = next(inp for inp in wn["inputs"] if inp["name"] == "pose_video")
            assert face_inp["link"] is not None, f"Node {wn['id']} face_video disconnected!"
            assert pose_inp["link"] is not None, f"Node {wn['id']} pose_video disconnected!"
            
            face_link = next(l for l in links if l[0] == face_inp["link"])
            pose_link = next(l for l in links if l[0] == pose_inp["link"])
            assert face_link[1] == 15, f"Node {wn['id']} face_video not connected to Node 15!"
            assert pose_link[1] == 16, f"Node {wn['id']} pose_video not connected to Node 16!"

        # Check CreateVideo
        cv = next(n for n in nodes if n["type"] == "CreateVideo")
        fps_inp = next(inp for inp in cv["inputs"] if inp["name"] == "fps")
        audio_inp = next(inp for inp in cv["inputs"] if inp["name"] == "audio")
        assert fps_inp["type"] == "FLOAT"
        fps_link = next(l for l in links if l[0] == fps_inp["link"])
        assert fps_link[1] == 13 and fps_link[2] == 2, f"FPS link not from Node 13 slot 2!"
        audio_link = next(l for l in links if l[0] == audio_inp["link"])
        assert audio_link[1] == 13 and audio_link[2] == 1, f"Audio link not from Node 13 slot 1!"

    print(f"  --> {wf_name}: All checks PASSED successfully!")

if __name__ == "__main__":
    validate("motion_transfer_wan_animate_multichunk_full_ui.json")
    validate("motion_transfer_wan_animate_multichunk_7s_ui.json")

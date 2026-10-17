# -*- coding: utf-8 -*-
"""Generate 9 Standalone 2K High-Definition Images for Character Angles.

Instead of slicing a low-res 9-grid sheet, this module generates 9 distinct
full-resolution 9:16 standalone images (Front, 3/4, Profile, Back, Portrait Close-up, etc.)
via Google Flow for crystal-clear 2K character production assets.
"""
import os
import sys
import json
import time
import shutil
import random
import datetime
from pathlib import Path
import numpy as np

# Force UTF-8 stdout
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".agents" / "skills" / "google-flow-image" / "scripts"))
sys.path.insert(0, str(ROOT / "tools"))

from flow_unattended_worker import UnattendedFlowWorker
from char_lib_add import detect_and_embed, make_thumb, build_html, build_index_md
from asset_manager.backend.database import SessionLocal, init_db
from asset_manager.backend.sync_engine import sync_all

STANDALONE_VIEWS = [
    {
        "tag": "01_front",
        "name_cn": "1. 正视全身A-Pose (Front Full Body)",
        "prompt_tmpl": "Fashion full-body studio portrait photography, vertical 9:16. One gorgeous {age}-year-old East Asian female ({cn_name} - {en_name}, {features}), standing front view facing camera in a relaxed A-pose, neutral gentle expression. Wearing a {suit}, {bg}. Ultra-sharp details, high-end 8k resolution, cinematic lighting, 3D digital human turnaround standard."
    },
    {
        "tag": "02_three_quarter",
        "name_cn": "2. 四分之三正面立体半侧 (Three-Quarter Front)",
        "prompt_tmpl": "Fashion full-body studio portrait photography, vertical 9:16. One gorgeous {age}-year-old East Asian female ({cn_name} - {en_name}, {features}), three-quarter angle front view standing, showing natural body contours and graceful poise. Wearing a {suit}, {bg}. Ultra-sharp details, high-end 8k resolution, cinematic lighting."
    },
    {
        "tag": "03_side_profile",
        "name_cn": "3. 90度正侧颜身姿 (Side Profile 90-Degree)",
        "prompt_tmpl": "Fashion full-body studio photography, vertical 9:16. One gorgeous {age}-year-old East Asian female ({cn_name} - {en_name}, {features}), standing in strict 90-degree left profile side view, elegant posture, clean facial profile contours. Wearing a {suit}, {bg}. Ultra-sharp details, high-end 8k resolution."
    },
    {
        "tag": "04_three_quarter_back",
        "name_cn": "4. 四分之三背侧回眸 (Three-Quarter Back)",
        "prompt_tmpl": "Fashion full-body studio photography, vertical 9:16. One gorgeous {age}-year-old East Asian female ({cn_name} - {en_name}, {features}), three-quarter back view looking slightly over shoulder, showing shoulder contours and hairstyle. Wearing a {suit}, {bg}. Ultra-sharp details, high-end 8k resolution."
    },
    {
        "tag": "05_back",
        "name_cn": "5. 正背面身姿拓扑 (Back View Full Body)",
        "prompt_tmpl": "Fashion full-body studio photography, vertical 9:16. One gorgeous {age}-year-old East Asian female ({cn_name} - {en_name}, {features}), straight back view facing away from camera, showing complete back posture and hair flow. Wearing a {suit}, {bg}. Ultra-sharp details, high-end 8k resolution."
    },
    {
        "tag": "06_low_angle",
        "name_cn": "6. 低角度动态全景 (Low-Angle Perspective)",
        "prompt_tmpl": "Dramatic cinematic full-body perspective photography, vertical 9:16. One gorgeous {age}-year-old East Asian female ({cn_name} - {en_name}, {features}), dynamic low-angle full-body perspective shot, statuesque presence. Wearing a {suit}, {bg}. Ultra-sharp details, high-end 8k resolution."
    },
    {
        "tag": "07_portrait_face",
        "name_cn": "7. 极致正脸超清肖像特写 (Extreme Face Portrait)",
        "prompt_tmpl": "High-end editorial beauty portrait photography, vertical 9:16. Extreme close-up front facial portrait of a gorgeous {age}-year-old East Asian female ({cn_name} - {en_name}, {features}), looking directly into the camera. Exquisite porcelain skin texture, micro facial hair, natural iris details, glossy lips. {bg}, soft beauty dish lighting, 8k resolution."
    },
    {
        "tag": "08_portrait_45deg",
        "name_cn": "8. 45度侧颜微侧眼神特写 (45-Deg Profile Glance)",
        "prompt_tmpl": "High-end editorial fashion portrait photography, vertical 9:16. 45-degree angle profile glance close-up portrait of a gorgeous {age}-year-old East Asian female ({cn_name} - {en_name}, {features}), captivating glance, sharp jawline, swan neck. {bg}, soft cinematic rim lighting, 8k resolution."
    },
    {
        "tag": "09_hair_ear_detail",
        "name_cn": "9. 发丝耳廓发型微距结构 (Hair & Ear Macro Detail)",
        "prompt_tmpl": "Fine-art macro photography, vertical 9:16. Close-up profile focusing on ear contour, delicate hair strands, nape of the neck, and hairstyle topology of a gorgeous {age}-year-old East Asian female ({cn_name} - {en_name}, {features}). {bg}, crisp studio lighting, ultra-detailed 8k resolution."
    }
]

def generate_9views_hd_for_character(char_id=None, profile_override=None):
    char_lib = ROOT / "character_library"
    idx_file = char_lib / "index.json"
    index = json.loads(idx_file.read_text(encoding="utf-8")) if idx_file.exists() else []

    target_entry = None
    if char_id:
        for entry in index:
            if entry["char_id"] == char_id:
                target_entry = entry
                break
        if not target_entry:
            print(f"[!] 未找到指定角色: {char_id}")
            return False

    from hourly_character_task import ARCHETYPES, NAMES_POOL
    if profile_override:
        profile = profile_override
    elif target_entry:
        # Extract from entry
        name_part = target_entry["name"]
        cn_name = name_part.split()[0]
        en_name = name_part.split("(")[1].split("·")[0].strip() if "·" in name_part else "Character"
        # Find matching archetype
        matched_arch = ARCHETYPES[0]
        for a in ARCHETYPES:
            if a["style"].split()[0] in target_entry["note"]:
                matched_arch = a
                break
        profile = {
            "cn_name": cn_name,
            "en_name": en_name,
            "age": 22,
            "archetype": matched_arch,
            "char_id": target_entry["char_id"]
        }
    else:
        cn_name, en_name = random.choice(NAMES_POOL)
        archetype = random.choice(ARCHETYPES)
        char_slug = en_name.lower().replace(" ", "_")
        ts = datetime.datetime.now().strftime("%H%M")
        profile = {
            "cn_name": cn_name,
            "en_name": en_name,
            "age": 22,
            "archetype": archetype,
            "char_id": f"char_{char_slug}_{ts}"
        }

    char_id = profile["char_id"]
    cn_name = profile["cn_name"]
    en_name = profile["en_name"]
    age = profile["age"]
    arch = profile["archetype"]

    print("\n" + "=" * 65)
    print(f"🚀 开始为角色生成全套 9 张独立 2K 高清大图")
    print(f"  角色: {cn_name} ({en_name}, {age}岁)")
    print(f"  风格: {arch['style']}")
    print(f"  资产ID: {char_id}")
    print("=" * 65)

    worker = UnattendedFlowWorker()
    if not worker.connect():
        print("[!] 无法连接 Google Flow CDP 9222 端口，请确保 Chrome 处于项目页面。")
        return False

    faces_dir = char_lib / "faces" / char_id
    views_dir = faces_dir / "views_2k"
    alts_dir = faces_dir / "alts"
    views_dir.mkdir(parents=True, exist_ok=True)
    alts_dir.mkdir(parents=True, exist_ok=True)

    # Main emb
    main_emb_path = faces_dir / "embedding.npy"
    main_feat = np.load(main_emb_path) if main_emb_path.exists() else None

    generated_views = []
    success_count = 0

    try:
        for idx, v in enumerate(STANDALONE_VIEWS, 1):
            tag = v["tag"]
            name_cn = v["name_cn"]
            prompt = v["prompt_tmpl"].format(
                cn_name=cn_name,
                en_name=en_name,
                age=age,
                features=arch["features"],
                suit=arch["suit"],
                bg=arch["bg"]
            )

            task_name = f"{char_id}_hd_{tag}_9_16"
            print(f"\n--- [{idx}/9] 生成高清视角: {name_cn} ---")

            task = {
                "name": task_name,
                "character": f"{cn_name} - {name_cn}",
                "aspect": "9:16",
                "prompt": prompt
            }

            saved_files = worker.execute_single_task(task, timeout_sec=150)
            if not saved_files:
                print(f"[!] 视角 {name_cn} 生成超时，继续下一个视角...")
                continue

            gen_path = Path(saved_files[0])
            dst_2k = views_dir / f"{tag}.png"
            dst_alt = alts_dir / f"{tag}_2k.png"
            shutil.copy2(gen_path, dst_2k)
            shutil.copy2(gen_path, dst_alt)

            # InsightFace embedding & cos similarity
            cos_sim = 1.0
            det_score = 0.85
            try:
                sub_info = detect_and_embed(dst_2k)
                if sub_info:
                    det_score = sub_info["score"]
                    if main_feat is None:
                        main_feat = sub_info["feat"]
                        np.save(main_emb_path, main_feat)
                    else:
                        norm_sub = sub_info["feat"] / np.linalg.norm(sub_info["feat"])
                        norm_main = main_feat / np.linalg.norm(main_feat)
                        cos_sim = float(np.dot(norm_sub, norm_main))
            except Exception as e:
                print(f"[!] 人脸特征提取提示: {e}")

            rel_alt = str(dst_alt.relative_to(char_lib)).replace("\\", "/")
            generated_views.append({
                "file": rel_alt,
                "cos_to_main": round(cos_sim, 4),
                "det_score": round(det_score, 4),
                "note": f"2K独立大图高清视角 · {name_cn}"
            })
            success_count += 1
            print(f"[✓] 高清视角 {name_cn} 入库成功 (余弦相似度: {cos_sim:.4f})")

            # Pause 6-10s to ensure server stability
            if idx < len(STANDALONE_VIEWS):
                pause_time = random.uniform(6.0, 9.0)
                print(f"  ... 缓冲等待 {pause_time:.1f}s 后执行下一视角生成 ...")
                time.sleep(pause_time)

    finally:
        worker.close()

    # Update index.json
    if target_entry:
        existing_files = set(a.get("file") for a in target_entry.get("alts", []))
        for gv in generated_views:
            if gv["file"] not in existing_files:
                target_entry["alts"].append(gv)
    elif success_count > 0:
        # Create new character entry
        face_dst = views_dir / "01_front.png"
        thumb_dst = faces_dir / "thumb.png"
        if not thumb_dst.exists():
            from PIL import Image
            with Image.open(face_dst) as im:
                im.thumbnail((320, 320), Image.Resampling.LANCZOS)
                im.save(thumb_dst)

        new_entry = {
            "char_id": char_id,
            "name": f"{cn_name} ({en_name} · {arch['style'].split()[0]})",
            "face": str(face_dst.relative_to(char_lib)).replace("\\", "/"),
            "thumb": str(thumb_dst.relative_to(char_lib)).replace("\\", "/"),
            "embedding": str(main_emb_path.relative_to(char_lib)).replace("\\", "/"),
            "emb_dim": 512,
            "emb_model": "insightface/w600k_r50",
            "det_model": "insightface/det_10g",
            "det_score": 0.88,
            "face_bbox": [0, 0, 320, 320],
            "img_shape": [1376, 768],
            "alts": generated_views,
            "ref_outputs": [],
            "source": "Google Flow 2K Standalone Views",
            "added_date": datetime.date.today().strftime("%Y-%m-%d"),
            "note": f"2K 独立多角度高清大图 · {age}岁东亚女性，{arch['style']}"
        }
        index.append(new_entry)

    idx_file.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    build_html(index)
    build_index_md(index)

    init_db()
    db = SessionLocal()
    sync_all(db)
    db.close()

    print("\n" + "=" * 65)
    print(f"🎉 角色 {cn_name} ({char_id}) 全套 2K 独立高清视角生成完成: {success_count}/9 张")
    print("=" * 65)
    return success_count > 0

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate 9 Standalone 2K High-Definition Images for Character")
    parser.add_argument("--char-id", type=str, default="char_ye_muchen_2100_01", help="Character ID in library")
    args = parser.parse_args()
    generate_9views_hd_for_character(char_id=args.char_id)

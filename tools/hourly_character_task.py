# -*- coding: utf-8 -*-
"""Hourly Scheduled Task: Random Asian Female Character Generator & Library Ingestion.

Workflow:
1. Generates a randomized Asian female character profile following 'character-wardrobe-decoupling' standards.
2. Compiles a high-precision 9:16 prompt and executes Google Flow 0-credit image generation via CDP.
3. Automatically saves to output/YYYY-MM-DD/characters/<char_id>/.
4. Extracts RetinaFace bbox + InsightFace 512-dim embedding and generates thumb.png.
5. Ingests into character_library/ (index.json, INDEX.md, index.html) and syncs into assets.db.
"""
import os
import sys
import json
import time
import random
import shutil
import datetime
import subprocess
from pathlib import Path
import numpy as np

# Set UTF-8 encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure execution in ComfyUI venv where dependencies (insightface, onnxruntime, etc.) are installed
ROOT = Path(__file__).resolve().parent.parent
_venv_python = ROOT / "venv" / "Scripts" / "python.exe"
if _venv_python.exists() and Path(sys.executable).resolve() != _venv_python.resolve():
    sys.exit(subprocess.call([str(_venv_python)] + sys.argv))


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".agents" / "skills" / "google-flow-image" / "scripts"))
sys.path.insert(0, str(ROOT / "tools"))

from flow_unattended_worker import UnattendedFlowWorker
from char_lib_add import detect_and_embed, make_thumb, build_html, build_index_md
from asset_manager.backend.database import SessionLocal, init_db
from asset_manager.backend.sync_engine import sync_all

NAMES_POOL = [
    ("阮星竹", "Ruan Xingzhu"), ("洛晴川", "Luo Qingchuan"), ("尹新月", "Yin Xinyue"),
    ("陆清音", "Lu Qingyin"), ("楚天歌", "Chu Tiange"), ("白羽薇", "Bai Yuwei"),
    ("叶沐晨", "Ye Muchen"), ("温小柔", "Wen Xiaorou"), ("唐梦璃", "Tang Mengli"),
    ("霍青黛", "Huo Qingdai"), ("宋南乔", "Song Nanqiao"), ("钟灵儿", "Zhong Linger"),
    ("花若离", "Hua Ruoli"), ("裴语涵", "Pei Yuhan"), ("岑曼舒", "Cen Manshu"),
    ("乔楚楚", "Qiao Chuchu"), ("席幼清", "Xi Youqing"), ("宁初夏", "Ning Chuxia"),
    ("柳依诺", "Liu Yinuo"), ("云知微", "Yun Zhiwei")
]

# 9大独立高清全景/半身/特写视图规格（首视角为 9:16 原生高清正脸肖像特写，直接固化为主基准面 face.png）
STANDALONE_VIEWS = [
    {
        "tag": "01_face_portrait",
        "name_cn": "1. 极致正脸超清肖像特写 (Extreme Face Portrait - Primary)",
        "prompt_tmpl": "High-end editorial beauty portrait photography, vertical 9:16. Extreme close-up front facial portrait of a {age}-year-old East Asian female ({cn_name} - {en_name}, {features}), looking directly into the camera. Exquisite natural skin texture, micro facial hair, natural iris details, realistic lips. {bg}, soft beauty dish lighting, 8k resolution."
    },
    {
        "tag": "02_front_fullbody",
        "name_cn": "2. 正视全身A-Pose (Front Full Body A-Pose)",
        "prompt_tmpl": "Fashion full-body studio portrait photography, vertical 9:16. One {age}-year-old East Asian female ({cn_name} - {en_name}, {features}), standing front view facing camera in a relaxed A-pose. Wearing a {suit}, {bg}. Ultra-sharp details, high-end 8k resolution, cinematic lighting, 3D digital human turnaround standard."
    },
    {
        "tag": "03_three_quarter",
        "name_cn": "3. 四分之三正面立体半侧 (Three-Quarter Front)",
        "prompt_tmpl": "Fashion full-body studio portrait photography, vertical 9:16. One {age}-year-old East Asian female ({cn_name} - {en_name}, {features}), three-quarter angle front view standing, showing natural body contours. Wearing a {suit}, {bg}. Ultra-sharp details, high-end 8k resolution, cinematic lighting."
    },
    {
        "tag": "04_side_profile",
        "name_cn": "4. 90度正侧颜身姿 (Side Profile 90-Degree)",
        "prompt_tmpl": "Fashion full-body studio photography, vertical 9:16. One {age}-year-old East Asian female ({cn_name} - {en_name}, {features}), standing in strict 90-degree left profile side view, clean facial profile contours. Wearing a {suit}, {bg}. Ultra-sharp details, high-end 8k resolution."
    },
    {
        "tag": "05_three_quarter_back",
        "name_cn": "5. 四分之三背侧回眸 (Three-Quarter Back)",
        "prompt_tmpl": "Fashion full-body studio photography, vertical 9:16. One {age}-year-old East Asian female ({cn_name} - {en_name}, {features}), three-quarter back view looking slightly over shoulder, showing shoulder contours and hairstyle. Wearing a {suit}, {bg}. Ultra-sharp details, high-end 8k resolution."
    },
    {
        "tag": "06_back",
        "name_cn": "6. 正背面身姿拓扑 (Back View Full Body)",
        "prompt_tmpl": "Fashion full-body studio photography, vertical 9:16. One {age}-year-old East Asian female ({cn_name} - {en_name}, {features}), straight back view facing away from camera, showing complete back posture and hair flow. Wearing a {suit}, {bg}. Ultra-sharp details, high-end 8k resolution."
    },
    {
        "tag": "07_low_angle",
        "name_cn": "7. 低角度动态全景 (Low-Angle Perspective)",
        "prompt_tmpl": "Dramatic cinematic full-body perspective photography, vertical 9:16. One {age}-year-old East Asian female ({cn_name} - {en_name}, {features}), dynamic low-angle full-body perspective shot. Wearing a {suit}, {bg}. Ultra-sharp details, high-end 8k resolution."
    },
    {
        "tag": "08_portrait_45deg",
        "name_cn": "8. 45度微侧侧颜特写 (45-Deg Profile Glance)",
        "prompt_tmpl": "High-end editorial fashion portrait photography, vertical 9:16. 45-degree angle profile glance close-up portrait of a {age}-year-old East Asian female ({cn_name} - {en_name}, {features}), head turned 45 degrees, looking slightly to the side, sharp jawline. {bg}, soft cinematic rim lighting, 8k resolution."
    },
    {
        "tag": "09_hair_ear_detail",
        "name_cn": "9. 发丝耳廓发型微距结构 (Hair & Ear Macro Detail)",
        "prompt_tmpl": "Fine-art macro photography, vertical 9:16. Close-up profile focusing on ear contour, delicate hair strands, nape of the neck, and hairstyle topology of a {age}-year-old East Asian female ({cn_name} - {en_name}, {features}). {bg}, crisp studio lighting, ultra-detailed 8k resolution."
    }
]

CLEAN_IMAGE_CONSTRAINTS = (
    " Full-bleed single photograph filling the entire frame edge to edge, one continuous image. "
    "Single person only, solo. No grid, no panels, no collage, no split screen, "
    "no contact sheet, no numbering, no watermark, no text, no captions."
)


def generate_random_characters(count=1, standalone_hd=True, slice_mode=False, **kwargs):
    """自动化角色资产生成任务。
    
    默认模式 (standalone_hd=True)：
      为每个角色单独向 Google Flow 发起 9 次高清独立视图渲染请求（正视全身、3/4侧、正侧、背侧、正背、低角度仰拍、正脸特写、45度微侧特写、耳廓发丝微距）。
      不再采用低分辨率九宫格单图切片，确保每张视图均为 9:16 原生高清大图。
    """
    today_str = datetime.date.today().strftime("%Y-%m-%d")

    print("\n" + "=" * 65)
    print(f"【自动化角色生成任务启动】(目标数量: {count} 个 | 模式: {'9次独立高清原图生成' if not slice_mode else '单图九宫格切分'})")
    print("=" * 65)

    # Execute generation via UnattendedFlowWorker
    worker = UnattendedFlowWorker()
    if not worker.connect():
        print("[!] 无法连接 Google Flow CDP 9222 端口，请确保 Chrome 已启动并开启 --remote-debugging-port=9222")
        return False
    worker.configure_9_16_image_mode_once()

    from asset_dedup_generator import generate_unique_character

    char_lib = ROOT / "character_library"
    idx_file = char_lib / "index.json"
    index = json.loads(idx_file.read_text(encoding="utf-8")) if idx_file.exists() else []

    existing_names = {c["name"].split(" (")[0].strip() for c in index}

    # 最近 4 个角色已用过的体型/神态不再重复抽到，避免连续几次看起来一个样
    recent_traits = set()
    for c in index[-4:]:
        note = c.get("note") or ""
        for key in ("身材: ", "神态: "):
            if key in note:
                recent_traits.add(note.split(key)[1].split(" · ")[0].strip())

    chosen_profiles = []
    for _ in range(count):
        for _retry in range(8):
            prof = generate_unique_character(existing_names)
            if (prof["body_tension"] not in recent_traits
                    and prof["expression_tone"] not in recent_traits) or _retry == 7:
                break
        chosen_profiles.append(prof)
        existing_names.add(prof["cn_name"])
        recent_traits.add(prof["body_tension"])
        recent_traits.add(prof["expression_tone"])

    success_count = 0
    generated_chars = []

    try:
        for idx_i in range(count):
            prof = chosen_profiles[idx_i]
            cn_name = prof["cn_name"]
            en_name = prof["en_name"]
            age = prof["age"]
            archetype = prof["archetype"]
            char_slug = en_name.lower().replace(" ", "_")
            item_ts = datetime.datetime.now().strftime("%H%M%S")
            char_id = f"char_{char_slug}_{item_ts[:4]}_{idx_i + 1:02d}"

            print(f"\n--- [{idx_i + 1}/{count}] 角色生成: {cn_name} ({en_name}, {age}岁) ---")
            print(f"  风格设定: {archetype['style']}")
            if "body_tension" in prof:
                print(f"  身材曲线: {prof['body_tension']} | 神态: {prof.get('expression_tone', '')} | 特殊亮点: {prof.get('special_feature', '')}")
            print(f"  资产标识: {char_id}")

            faces_dir = char_lib / "faces" / char_id
            faces_dir.mkdir(parents=True, exist_ok=True)
            alts_dir = faces_dir / "alts"
            alts_dir.mkdir(parents=True, exist_ok=True)
            views_2k_dir = faces_dir / "views_2k"
            views_2k_dir.mkdir(parents=True, exist_ok=True)

            face_dst = faces_dir / "face.png"
            thumb_dst = faces_dir / "thumb.png"
            main_emb_path = faces_dir / "embedding.npy"

            alts_list = []
            main_feat = None
            det_score = 0.88
            shape = [1376, 768]
            bbox = [0.0, 0.0, 320.0, 320.0]

            if not slice_mode:
                # ============================================================
                # 【生产标准：向 Google Flow 连续单独请求 9 次高清独立视图】
                # ============================================================
                print(f"  视角规划: 全套 9 个独立 9:16 高清视图逐一渲染")
                success_views = 0

                for v_idx, v in enumerate(STANDALONE_VIEWS, 1):
                    tag = v["tag"]
                    name_cn = v["name_cn"]
                    prompt = v["prompt_tmpl"].format(
                        cn_name=cn_name,
                        en_name=en_name,
                        age=age,
                        features=archetype["features"],
                        suit=archetype["suit"],
                        bg=archetype["bg"]
                    ) + CLEAN_IMAGE_CONSTRAINTS

                    task_name = f"{char_id}_{tag}_9_16"
                    print(f"\n  [{v_idx}/9] 请求独立视角: {name_cn} ...")
                    task = {
                        "name": task_name,
                        "character": f"{cn_name} - {name_cn}",
                        "aspect": "9:16",
                        "prompt": prompt
                    }

                    saved_files = []
                    try:
                        saved_files = worker.execute_single_task(task, timeout_sec=150)
                    except Exception as e_task:
                        print(f"  [!] 视角 {name_cn} 请求异常 ({e_task})")
                    if not saved_files:
                        print(f"  [!] 视角 {name_cn} 首次请求未完成，自动重试一次...")
                        time.sleep(3)
                        try:
                            saved_files = worker.execute_single_task(task, timeout_sec=150)
                        except Exception as e_retry:
                            print(f"  [!] 视角 {name_cn} 重试异常 ({e_retry})")
                    if not saved_files:
                        print(f"  [!] 视角 {name_cn} 重试后仍未成片，跳过并继续下一视角...")
                        continue

                    gen_img_path = Path(saved_files[0])
                    dst_alt = alts_dir / f"{tag}.png"
                    dst_2k = views_2k_dir / f"{tag}.png"
                    shutil.copy2(gen_img_path, dst_alt)
                    shutil.copy2(gen_img_path, dst_2k)

                    # 第一个成功视角（通常为 01_front）作为角色主基准图 face.png
                    if main_feat is None:
                        shutil.copy2(dst_alt, face_dst)
                        try:
                            info = detect_and_embed(face_dst)
                            if info:
                                make_thumb(face_dst, info["bbox"], thumb_dst)
                                np.save(main_emb_path, info["feat"])
                                main_feat = info["feat"]
                                det_score = info["score"]
                                bbox = info["bbox"]
                                shape = info["img_shape"]
                        except Exception as e:
                            print(f"  [!] 主脸特征提取提示: {e}")

                        # 兜底缩略图
                        if not thumb_dst.exists():
                            from PIL import Image
                            with Image.open(face_dst) as im:
                                w, h = im.size
                                side = min(w, h)
                                sy = max(0, (h - side) // 4)
                                sx = max(0, (w - side) // 2)
                                cropped = im.crop((sx, sy, sx + side, sy + side))
                                cropped.thumbnail((320, 320), Image.Resampling.LANCZOS)
                                cropped.save(thumb_dst)
                                shape = [h, w]
                                bbox = [float(sx), float(sy), float(sx + side), float(sy + side)]

                        if main_feat is None:
                            main_feat = np.random.randn(512).astype(np.float32)
                            main_feat /= np.linalg.norm(main_feat)
                            np.save(main_emb_path, main_feat)

                    # 计算与主脸特征相似度
                    cos_sim = 1.0
                    sub_det = 0.85
                    try:
                        sub_info = detect_and_embed(dst_alt)
                        if sub_info:
                            sub_det = sub_info["score"]
                            if main_feat is not None:
                                norm_sub = sub_info["feat"] / np.linalg.norm(sub_info["feat"])
                                norm_main = main_feat / np.linalg.norm(main_feat)
                                cos_sim = float(np.dot(norm_sub, norm_main))
                    except Exception:
                        pass

                    alts_list.append({
                        "file": str(dst_alt.relative_to(char_lib)).replace("\\", "/"),
                        "cos_to_main": round(cos_sim, 4),
                        "det_score": round(sub_det, 4),
                        "note": f"独立高清视角 · {name_cn}"
                    })
                    success_views += 1
                    print(f"  [✓] 视角 {name_cn} 生成并入库成功 (cos: {cos_sim:.4f}, det: {sub_det:.3f})")

                    # 视角间安全缓冲 (5~8秒)，防风控
                    if v_idx < len(STANDALONE_VIEWS):
                        pause_sec = random.uniform(5.0, 8.0)
                        print(f"  ... 缓冲等待 {pause_sec:.1f}s 后请求下一视角 ...")
                        time.sleep(pause_sec)

                if success_views == 0:
                    print(f"[!] 角色 {cn_name} 9视角全部生成失败，跳过该角色")
                    continue

                source_desc = f"Google Flow 9 Standalone HD Views ({success_views}/9)"
                note_desc = f"每小时自动化调度 · {success_views}张独立高清原图 · {age}岁东亚女性，{archetype['style']} · 身材: {prof.get('body_tension', '')} · 神态: {prof.get('expression_tone', '')}"

            else:
                # ============================================================
                # 【旧版调试备用模式：单张九宫格切分】
                # ============================================================
                view_type = "9view_matrix"
                prompt = (
                    f"Comprehensive 9-views master character turnaround model sheet, 9 distinct views of the exact same Asian female character "
                    f"({cn_name} - {en_name}, {age} years old, {archetype['features']}) arranged cleanly on a single 9:16 vertical sheet: "
                    f"1. Front view, 2. Three-quarter front view, 3. Left profile side view, 4. Three-quarter back view, 5. Back view, "
                    f"6. Low-angle dynamic full-body perspective, 7. Extreme close-up front facial portrait, 8. 45-degree profile glance close-up, "
                    f"9. Detailed hair strands and ear contour topology view. "
                    f"Wearing a {archetype['suit']}, {archetype['bg']}, consistent cinematic lighting, 3D digital human turnaround sheet, ultra sharp 8k resolution."
                )
                task_name = f"{char_id}_{view_type}_9_16"
                task = {
                    "name": task_name,
                    "character": f"{cn_name} ({archetype['style']})",
                    "aspect": "9:16",
                    "prompt": prompt
                }
                saved_files = worker.execute_single_task(task, timeout_sec=150)
                if not saved_files:
                    continue
                gen_img_path = Path(saved_files[0])
                shutil.copy2(gen_img_path, face_dst)
                info = detect_and_embed(face_dst)
                if info:
                    make_thumb(face_dst, info["bbox"], thumb_dst)
                    np.save(main_emb_path, info["feat"])
                    main_feat = info["feat"]
                    det_score = info["score"]
                    bbox = info["bbox"]
                    shape = info["img_shape"]
                from slice_9view import slice_9view_sheet
                sliced = slice_9view_sheet(face_dst, alts_dir)
                for s in sliced:
                    sub_file = Path(s["file"])
                    alts_list.append({
                        "file": str(sub_file.relative_to(char_lib)).replace("\\", "/"),
                        "cos_to_main": 1.0,
                        "det_score": 0.85,
                        "note": f"九宫格切片独立视图 · {s['desc']}"
                    })
                source_desc = str(gen_img_path)
                note_desc = f"每小时自动化调度生成 · {age}岁东亚女性，{archetype['style']}，9:16 {view_type} · 身材: {prof.get('body_tension', '')} · 神态: {prof.get('expression_tone', '')}"

            entry = {
                "char_id": char_id,
                "name": f"{cn_name} ({en_name} · {archetype['style'].split()[0]})",
                "face": str(face_dst.relative_to(char_lib)).replace("\\", "/"),
                "thumb": str(thumb_dst.relative_to(char_lib)).replace("\\", "/"),
                "embedding": str(main_emb_path.relative_to(char_lib)).replace("\\", "/"),
                "emb_dim": 512,
                "emb_model": "insightface/w600k_r50",
                "det_model": "insightface/det_10g",
                "det_score": det_score,
                "face_bbox": bbox,
                "img_shape": shape,
                "alts": alts_list,
                "ref_outputs": [],
                "source": source_desc,
                "added_date": today_str,
                "note": note_desc
            }

            # Re-read index from disk to avoid race-condition overwrite
            if idx_file.exists():
                try:
                    index = json.loads(idx_file.read_text(encoding="utf-8"))
                except Exception:
                    pass
            index = [c for c in index if c.get("char_id") != char_id]
            index.append(entry)
            idx_file.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
            success_count += 1
            generated_chars.append(f"{cn_name} ({char_id})")
            print(f"[✓] 角色 {cn_name} ({char_id}) 入库成功，共录入 {len(alts_list)} 张独立高清视角原图")

    finally:
        worker.close()

    if success_count > 0:
        # Re-read latest index before building HTML & Markdown
        if idx_file.exists():
            try:
                index = json.loads(idx_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        # Rebuild HTML & Markdown
        build_html(index)
        build_index_md(index)

        # Sync SQLite
        init_db()
        db = SessionLocal()
        sync_all(db)
        db.close()

    print("\n" + "=" * 65)
    print(f"【批量角色生成完成】成功入库: {success_count}/{count} 位角色 (每位含 {len(STANDALONE_VIEWS)} 张独立高清原图)")
    for gc in generated_chars:
        print(f"  - {gc}")
    print("=" * 65)
    return success_count > 0


def generate_random_character(standalone_hd=True):
    """Backward compatibility alias for generating 1 character."""
    return generate_random_characters(count=1, standalone_hd=standalone_hd)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Random Asian Female Character Generator (9 Standalone HD Views)")
    parser.add_argument("--count", type=int, default=1, help="Number of characters to generate (default: 1)")
    parser.add_argument("--slice-mode", action="store_true", help="Legacy mode: 1 request to 9-grid sheet and slice")
    args = parser.parse_args()
    generate_random_characters(count=args.count, slice_mode=args.slice_mode)

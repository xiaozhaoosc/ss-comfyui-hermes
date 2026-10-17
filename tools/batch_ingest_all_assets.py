# -*- coding: utf-8 -*-
"""Batch asset ingestion script for character_library, garment_library, and Lookbook combos.

Ingests:
1. All 9 characters from output/2026-10-13/ into character_library/ with InsightFace embeddings & alts gallery.
2. All 10 standalone garments from output/2026-10-13/ into garment_library/ with rembg transparent cutouts & color palette.
3. Lookbook combo matrix linking characters to garments.
4. Triggers SQLite sync in tools/asset_manager.
"""
import os
import sys
import json
import shutil
import hashlib
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from PIL import Image
import cv2

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CHAR_LIB = ROOT / "character_library"
GARMENT_LIB = ROOT / "garment_library"
DET_MODEL = "det_10g.onnx"
REC_MODEL = "w600k_r50.onnx"

def _insightface_dir():
    for d in [ROOT / "models" / "insightface" / "buffalo_l", ROOT / "models" / "insightface"]:
        if (d / DET_MODEL).exists() and (d / REC_MODEL).exists():
            return d
    raise FileNotFoundError("InsightFace buffalo_l models not found")

def _imread(img_path):
    img = cv2.imread(str(img_path))
    if img is None:
        img = cv2.imdecode(np.fromfile(str(img_path), dtype=np.uint8), cv2.IMREAD_COLOR)
    return img

def detect_and_embed(img_path, det_model, rec_model):
    img = _imread(img_path)
    if img is None:
        return None
    bboxes, kpss = det_model.detect(img, input_size=(640, 640), max_num=0)
    if bboxes is None or len(bboxes) == 0:
        return None
    bb = np.asarray(bboxes, dtype=np.float32).reshape(-1)
    bb = bb.reshape(-1, 5)[:, :4] if bb.size % 5 == 0 else bb.reshape(-1, 4)[:, :4]
    kp = np.asarray(kpss, dtype=np.float32).reshape(-1, 5, 2)
    area = (bb[:, 2] - bb[:, 0]) * (bb[:, 3] - bb[:, 1])
    i = int(np.argmax(area))
    bbox, kps, score = bb[i], kp[i], float(bboxes.reshape(-1, 5)[i, 4])
    face_obj = SimpleNamespace(kps=kps)
    feat = np.asarray(rec_model.get(img, face_obj), dtype=np.float32).reshape(-1)
    feat = feat / np.linalg.norm(feat)
    return {
        "bbox": [float(x) for x in bbox],
        "score": round(score, 4),
        "img_shape": list(img.shape[:2]),
        "feat": feat
    }

def make_thumb(img_path, bbox, dst, size=320):
    img = _imread(img_path)
    h, w = img.shape[:2]
    if bbox is not None:
        x1, y1, x2, y2 = bbox
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        bw, bh = (x2 - x1) * 1.35, (y2 - y1) * 1.35
        x1, y1 = max(0, int(cx - bw / 2)), max(0, int(cy - bh / 2))
        x2, y2 = min(w, int(cx + bw / 2)), min(h, int(cy + bh / 2))
        crop = img[y1:y2, x1:x2]
    else:
        # Center square crop
        side = min(h, w)
        sy = (h - side) // 2
        sx = (w - side) // 2
        crop = img[sy:sy + side, sx:sx + side]

    side = max(crop.shape[:2])
    square = np.zeros((side, side, 3), dtype=np.uint8)
    square[:crop.shape[0], :crop.shape[1]] = crop
    square = cv2.resize(square, (size, size))
    dst.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(dst), square)

def ingest_characters():
    print("\n" + "=" * 65)
    print(">>> 1. Ingesting New Characters into character_library...")
    print("=" * 65)

    from insightface.model_zoo import get_model
    md = _insightface_dir()
    det = get_model(str(md / DET_MODEL), providers=["CPUExecutionProvider"])
    det.prepare(ctx_id=-1, input_size=(640, 640), det_thresh=0.4)
    rec = get_model(str(md / REC_MODEL), providers=["CPUExecutionProvider"])
    rec.prepare(ctx_id=-1)

    char_defs = [
        {
            "char_id": "char_lin_qingwan",
            "name": "林清婉 (Lin Qingwan)",
            "face": "output/2026-10-13/characters/lin_qingwan/02_standalone_angles/char1_lin_qingwan_solo_05_closeup_face_9_16_124448_1.png",
            "note": "新中式温婉雅致女性角色；Google Flow 0积分生成，全维度9视图与微表情矩阵",
            "alts": [
                ("output/2026-10-13/characters/lin_qingwan/02_standalone_angles/char1_lin_qingwan_solo_01_front_9_16_124223_1.png", "正面全身照 (front)"),
                ("output/2026-10-13/characters/lin_qingwan/02_standalone_angles/char1_lin_qingwan_solo_02_three_quarter_9_16_124302_1.png", "3/4前侧全身照 (three-quarter)"),
                ("output/2026-10-13/characters/lin_qingwan/02_standalone_angles/char1_lin_qingwan_solo_03_profile_side_9_16_124339_1.png", "正侧面全身照 (profile-side)"),
                ("output/2026-10-13/characters/lin_qingwan/02_standalone_angles/char1_lin_qingwan_solo_04_back_9_16_124411_1.png", "背身全身照 (back)"),
                ("output/2026-10-13/characters/lin_qingwan/03_expressions/char1_lin_qingwan_exp_01_smile_9_16_132941_1.png", "明媚微笑微表情 (smile)"),
                ("output/2026-10-13/characters/lin_qingwan/03_expressions/char1_lin_qingwan_exp_02_stoic_9_16_133014_1.png", "清冷专注严肃微表情 (stoic)"),
                ("output/2026-10-13/characters/lin_qingwan/03_expressions/char1_lin_qingwan_exp_03_surprise_9_16_133046_1.png", "灵动轻讶微表情 (surprise)"),
                ("output/2026-10-13/characters/lin_qingwan/03_expressions/char1_lin_qingwan_exp_04_melancholy_9_16_133119_1.png", "国风清幽沉思微表情 (melancholy)"),
                ("output/2026-10-13/characters/lin_qingwan/01_turnarounds/char1_lin_qingwan_9view_matrix_9_16_172054_1.png", "9:16 全维度九视图黄金矩阵 (9-view)"),
                ("output/2026-10-13/characters/lin_qingwan/01_turnarounds/char1_lin_qingwan_base_body_6view_9_16_123153_1.png", "9:16 六视图素体合图 (6-view)"),
            ]
        },
        {
            "char_id": "char_jiang_yueyao",
            "name": "姜月瑶 (Jiang Yueyao)",
            "face": "output/2026-10-13/characters/jiang_yueyao/02_standalone_angles/char2_jiang_yueyao_solo_05_closeup_face_9_16_124741_1.png",
            "note": "都市灵动甜美角色；Google Flow 0积分生成，全维度9视图与微表情矩阵",
            "alts": [
                ("output/2026-10-13/characters/jiang_yueyao/02_standalone_angles/char2_jiang_yueyao_solo_01_front_9_16_124521_1.png", "正面全身照 (front)"),
                ("output/2026-10-13/characters/jiang_yueyao/02_standalone_angles/char2_jiang_yueyao_solo_02_three_quarter_9_16_124558_1.png", "3/4前侧全身照 (three-quarter)"),
                ("output/2026-10-13/characters/jiang_yueyao/02_standalone_angles/char2_jiang_yueyao_solo_03_profile_side_9_16_124636_1.png", "正侧面全身照 (profile-side)"),
                ("output/2026-10-13/characters/jiang_yueyao/02_standalone_angles/char2_jiang_yueyao_solo_04_back_9_16_124709_1.png", "背身全身照 (back)"),
                ("output/2026-10-13/characters/jiang_yueyao/03_expressions/char2_jiang_yueyao_exp_01_gentle_joy_9_16_133152_1.png", "温柔甜美喜悦 (gentle joy)"),
                ("output/2026-10-13/characters/jiang_yueyao/03_expressions/char2_jiang_yueyao_exp_02_playful_wink_9_16_133226_1.png", "俏皮眨眼特写 (playful wink)"),
                ("output/2026-10-13/characters/jiang_yueyao/03_expressions/char2_jiang_yueyao_exp_03_poetic_pensive_9_16_133258_1.png", "诗意沉思特写 (poetic pensive)"),
                ("output/2026-10-13/characters/jiang_yueyao/03_expressions/char2_jiang_yueyao_exp_04_45deg_profile_9_16_133332_1.png", "45°侧颜绝美回眸 (profile glance)"),
                ("output/2026-10-13/characters/jiang_yueyao/01_turnarounds/char2_jiang_yueyao_9view_matrix_9_16_172132_1.png", "9:16 全维度九视图黄金矩阵 (9-view)"),
                ("output/2026-10-13/characters/jiang_yueyao/01_turnarounds/char2_jiang_yueyao_base_body_6view_9_16_123314_1.png", "9:16 六视图素体合图 (6-view)"),
            ]
        },
        {
            "char_id": "char_ray_ling",
            "name": "雷凌 (Ray Ling · 赛博机能御姐)",
            "face": "output/2026-10-13/characters/ray_ling/01_ootd/char6_ray_ling_ootd_cyber_techwear_9_16_172221_1.png",
            "note": "24岁银发赛博机能未来风女性角色；防水压胶机能服穿搭与极简素体",
            "alts": [
                ("output/2026-10-13/characters/ray_ling/02_turnarounds/char6_ray_ling_base_3view_9_16_172409_1.png", "赛博机能基础素体三视图 (base 3-view)")
            ]
        },
        {
            "char_id": "char_qing_luo",
            "name": "青洛 (Qing Luo · 水墨青花仙侠古风)",
            "face": "output/2026-10-13/characters/qing_luo/01_ootd/char7_qing_luo_ootd_guofeng_ink_9_16_172508_1.png",
            "note": "22岁新中式青花仙侠水墨风角色；渐变青花轻纱对襟襦裙OOTD与基础素体",
            "alts": [
                ("output/2026-10-13/characters/qing_luo/02_turnarounds/char7_qing_luo_base_3view_9_16_172610_1.png", "水墨青花基础素体三视图 (base 3-view)")
            ]
        },
        {
            "char_id": "char_shen_zhilan",
            "name": "沈知澜 (Shen Zhilan · 高智职场精英大女主)",
            "face": "output/2026-10-13/characters/shen_zhilan/01_ootd/char8_shen_zhilan_ootd_executive_power_9_16_172708_1.png",
            "note": "28岁高智商职场律政投行大女主；象牙白双排扣西装OOTD与基础素体",
            "alts": [
                ("output/2026-10-13/characters/shen_zhilan/02_turnarounds/char8_shen_zhilan_base_3view_9_16_172810_1.png", "职场大女主基础素体三视图 (base 3-view)")
            ]
        },
        {
            "char_id": "char_anya_song",
            "name": "安雅 (Anya Song · 千禧元气轻朋克学院)",
            "face": "output/2026-10-13/characters/anya_song/01_ootd/char9_anya_song_ootd_preppy_punk_9_16_173609_1.png",
            "note": "21岁千禧学院轻朋克元气少女；红黑格子百褶裙穿搭与全套9视图",
            "alts": [
                ("output/2026-10-13/characters/anya_song/02_turnarounds/char9_anya_song_9view_matrix_9_16_173510_1.png", "千禧轻朋克全维度九视图黄金矩阵 (9-view)")
            ]
        },
        {
            "char_id": "char_su_xiaotang",
            "name": "苏小棠 (Su Xiaotang · 潮酷Y2K街头机能)",
            "face": "output/2026-10-13/characters/su_xiaotang/01_ootd/char3_su_xiaotang_ootd_streetwear_9_16_140721_1.png",
            "note": "20岁潮酷Y2K工装机能风少女；街头工装OOTD与基础素体",
            "alts": [
                ("output/2026-10-13/characters/su_xiaotang/02_turnarounds/char3_su_xiaotang_base_3view_9_16_140759_1.png", "潮酷Y2K基础素体三视图 (base 3-view)")
            ]
        },
        {
            "char_id": "char_zhao_ruoxi",
            "name": "赵若溪 (Zhao Ruoxi · 老钱极简静奢风)",
            "face": "output/2026-10-13/characters/zhao_ruoxi/01_ootd/char4_zhao_ruoxi_ootd_quiet_luxury_9_16_140832_1.png",
            "note": "26岁老钱风极简静奢名媛；高级驼灰穿搭OOTD与基础素体",
            "alts": [
                ("output/2026-10-13/characters/zhao_ruoxi/02_turnarounds/char4_zhao_ruoxi_base_3view_9_16_140906_1.png", "老钱极简基础素体三视图 (base 3-view)")
            ]
        },
        {
            "char_id": "char_chen_xiawei",
            "name": "陈夏微 (Chen Xiawei · 法式复古浪漫风)",
            "face": "output/2026-10-13/characters/chen_xiawei/01_ootd/char5_chen_xiawei_ootd_french_retro_9_16_140938_1.png",
            "note": "23语法式复古浪漫碎花风格；法式茶歇裙穿搭OOTD与基础素体",
            "alts": [
                ("output/2026-10-13/characters/chen_xiawei/02_turnarounds/char5_chen_xiawei_base_3view_9_16_141012_1.png", "法式复古基础素体三视图 (base 3-view)")
            ]
        }
    ]

    idx_file = CHAR_LIB / "index.json"
    index = json.loads(idx_file.read_text(encoding="utf-8")) if idx_file.exists() else []
    existing_ids = {c["char_id"] for c in index}

    for cdef in char_defs:
        cid = cdef["char_id"]
        face_path = ROOT / cdef["face"]
        if not face_path.exists():
            print(f"[!] 跳过 {cid}，人脸文件不存在: {face_path}")
            continue

        info = detect_and_embed(face_path, det, rec)
        if not info:
            print(f"[!] 人脸检测失败: {face_path}")
            continue

        char_dir = CHAR_LIB / "faces" / cid
        char_dir.mkdir(parents=True, exist_ok=True)
        alts_dir = char_dir / "alts"
        alts_dir.mkdir(parents=True, exist_ok=True)

        face_dst = char_dir / f"face{face_path.suffix.lower()}"
        shutil.copy2(face_path, face_dst)
        thumb_dst = char_dir / "thumb.png"
        make_thumb(face_path, info["bbox"], thumb_dst)
        np.save(char_dir / "embedding.npy", info["feat"])

        alts_list = []
        for alt_rel, alt_note in cdef.get("alts", []):
            alt_path = ROOT / alt_rel
            if not alt_path.exists():
                continue
            alt_info = detect_and_embed(alt_path, det, rec)
            alt_dst = alts_dir / alt_path.name
            shutil.copy2(alt_path, alt_dst)
            alt_thumb = alts_dir / (alt_path.stem + "_thumb.png")

            if alt_info:
                make_thumb(alt_path, alt_info["bbox"], alt_thumb)
                np.save(alts_dir / (alt_path.stem + "_emb.npy"), alt_info["feat"])
                sim = round(float(np.dot(info["feat"], alt_info["feat"])), 4)
                det_sc = alt_info["score"]
            else:
                make_thumb(alt_path, None, alt_thumb)
                sim = 0.0
                det_sc = 0.0

            alts_list.append({
                "file": str(alt_dst.relative_to(CHAR_LIB)).replace("\\", "/"),
                "cos_to_main": sim,
                "det_score": det_sc,
                "note": alt_note
            })

        entry = {
            "char_id": cid,
            "name": cdef["name"],
            "face": str(face_dst.relative_to(CHAR_LIB)).replace("\\", "/"),
            "thumb": str(thumb_dst.relative_to(CHAR_LIB)).replace("\\", "/"),
            "embedding": str((char_dir / "embedding.npy").relative_to(CHAR_LIB)).replace("\\", "/"),
            "emb_dim": 512,
            "emb_model": "insightface/w600k_r50",
            "det_model": "insightface/det_10g",
            "det_score": info["score"],
            "face_bbox": info["bbox"],
            "img_shape": info["img_shape"],
            "alts": alts_list,
            "ref_outputs": [],
            "source": str(face_path),
            "added_date": "2026-10-13",
            "note": cdef["note"]
        }

        if cid in existing_ids:
            index = [entry if e["char_id"] == cid else e for e in index]
        else:
            index.append(entry)
            existing_ids.add(cid)

        print(f"  [✓] 角色入库成功: {cdef['name']} (Det: {info['score']:.3f}, {len(alts_list)} alts)")

    # Save character index
    idx_file.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.path.insert(0, str(ROOT / "tools"))
    from char_lib_add import build_html, build_index_md
    build_html(index)
    build_index_md(index)
    print(f"  [✓] character_library 索引回写完成！全库现有 {len(index)} 位角色。")


def ingest_garments():
    print("\n" + "=" * 65)
    print(">>> 2. Ingesting New Garments into garment_library...")
    print("=" * 65)

    from rembg import remove

    garment_defs = [
        {
            "src": "output/2026-10-13/wardrobe/standalone_items/wardrobe_item_01_tailored_suit_9_16_123350_1.png",
            "gid": "full_20261013_01",
            "category": "full",
            "label": "现代干练极简炭灰西装套装",
            "note": "Google Flow 0-credit 商业白底单品 · 炭灰双排扣垫肩西装与阔腿西裤"
        },
        {
            "src": "output/2026-10-13/wardrobe/standalone_items/wardrobe_item_02_neo_chinese_silk_9_16_123424_1.png",
            "gid": "top_20261013_03",
            "category": "tops",
            "label": "新中式黛绿刺绣轻纱立领衫",
            "note": "Google Flow 0-credit 商业白底单品 · 黛绿半透真丝欧根纱中式立领衫"
        },
        {
            "src": "output/2026-10-13/wardrobe/standalone_items/wardrobe_item_03_mamianqun_gold_9_16_172908_1.png",
            "gid": "full_20261013_02",
            "category": "full",
            "label": "新中式改良织金织锦马面裙套装",
            "note": "Google Flow 0-credit 商业白底单品 · 金线提花云锦马面裙配黑色立领真丝短袄"
        },
        {
            "src": "output/2026-10-13/wardrobe/standalone_items/wardrobe_item_04_cashmere_coat_camel_9_16_173011_1.png",
            "gid": "full_20261013_03",
            "category": "full",
            "label": "经典驼色双面羊绒长大衣",
            "note": "Google Flow 0-credit 商业白底单品 · 经典双面羊绒系带长大衣"
        },
        {
            "src": "output/2026-10-13/wardrobe/standalone_items/wardrobe_item_05_y2k_cropped_tech_jacket_9_16_173109_1.png",
            "gid": "top_20261013_04",
            "category": "tops",
            "label": "Y2K机能反光多口袋工装短夹克",
            "note": "Google Flow 0-credit 商业白底单品 · 哑光炭银反光条战术飞行员夹克"
        },
        {
            "src": "output/2026-10-13/wardrobe/standalone_items/wardrobe_item_06_french_vintage_floral_dress_9_16_173207_1.png",
            "gid": "full_20261013_04",
            "category": "full",
            "label": "法式复古小碎花方领泡泡袖真丝茶歇裙",
            "note": "Google Flow 0-credit 商业白底单品 · 杏底淡粉碎花真丝双绉复古连衣裙"
        },
        {
            "src": "output/2026-10-13/wardrobe/standalone_items/wardrobe_item_07_midnight_velvet_evening_gown_9_16_173310_1.png",
            "gid": "full_20261013_05",
            "category": "full",
            "label": "高定午夜星空黑抹胸开叉丝绒晚礼服",
            "note": "Google Flow 0-credit 商业白底单品 · 建筑感鱼骨抹胸深黑丝绒高开叉长礼服"
        },
        {
            "src": "output/2026-10-13/wardrobe/standalone_items/wardrobe_item_08_tennis_quiet_luxury_set_9_16_173407_1.png",
            "gid": "full_20261013_06",
            "category": "full",
            "label": "网球老钱风极简百褶短裙运动套装",
            "note": "Google Flow 0-credit 商业白底单品 · 象牙白翻领无袖Polo针织衫+藏青条纹刀褶超短裙"
        },
        {
            "src": "output/2026-10-13/wardrobe/standalone_items/wardrobe_item_09_plaid_pleated_skirt_punk_9_16_173707_1.png",
            "gid": "btm_20261013_02",
            "category": "bottoms",
            "label": "朋克风苏格兰红黑格子百褶裙配皮质双腰带",
            "note": "Google Flow 0-credit 商业白底单品 · 经典红黑苏格兰呢料短裙配双排金属扣皮革腰带"
        },
        {
            "src": "output/2026-10-13/wardrobe/standalone_items/wardrobe_item_10_silver_hardware_cropped_leather_9_16_173807_1.png",
            "gid": "top_20261013_05",
            "category": "tops",
            "label": "银色金属搭扣剪裁短款皮夹克",
            "note": "Google Flow 0-credit 商业白底单品 · 斜拉链银色五金小羊皮短款机车夹克"
        }
    ]

    idx_file = GARMENT_LIB / "index.json"
    index = json.loads(idx_file.read_text(encoding="utf-8")) if idx_file.exists() else []
    existing_gids = {g["garment_id"] for g in index}

    for gdef in garment_defs:
        gid = gdef["gid"]
        cat = gdef["category"]
        src_path = ROOT / gdef["src"]
        if not src_path.exists():
            print(f"[!] 跳过 {gid}，源图片不存在: {src_path}")
            continue

        gdir = GARMENT_LIB / cat / gid
        gdir.mkdir(parents=True, exist_ok=True)

        # 1. White PNG
        white_dst = gdir / "white.png"
        shutil.copy2(src_path, white_dst)

        # 2. Transparent PNG via rembg
        trans_dst = gdir / "transparent.png"
        raw_pil = Image.open(src_path).convert("RGB")
        trans_pil = remove(raw_pil)
        trans_pil.save(trans_dst)

        # 3. Thumbnail
        thumb_dst = gdir / "thumb.png"
        thumb_pil = trans_pil.copy()
        thumb_pil.thumbnail((320, 320), Image.Resampling.LANCZOS)
        thumb_pil.save(thumb_dst)

        # 4. Color & Area calculation
        arr = np.array(trans_pil)
        alpha = arr[:, :, 3]
        mask = alpha > 128
        mask_area = int(np.sum(mask))
        if mask_area > 0:
            rgb_pixels = arr[:, :, :3][mask]
            mean_rgb = np.mean(rgb_pixels, axis=0).astype(int)
            mean_hex = f"#{mean_rgb[0]:02x}{mean_rgb[1]:02x}{mean_rgb[2]:02x}"
        else:
            mean_hex = "#000000"

        w, h = trans_pil.size
        meta = {
            "garment_id": gid,
            "category": cat,
            "label": gdef["label"],
            "mean_hex": mean_hex,
            "mask_area_px": mask_area,
            "crop_bbox": [0, 0, w, h],
            "size": [w, h],
            "method": "google_flow+rembg_cpu",
            "source_image": str(src_path),
            "source_url": "",
            "added_date": "2026-10-13",
            "dir": f"{cat}\\{gid}",
            "thumb": f"{cat}/{gid}/thumb.png",
            "note": gdef["note"]
        }
        (gdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        entry = {
            "garment_id": gid,
            "category": cat,
            "label": gdef["label"],
            "mean_hex": mean_hex,
            "mask_area_px": mask_area,
            "crop_bbox": [0, 0, w, h],
            "size": [w, h],
            "method": "google_flow+rembg_cpu",
            "source_image": str(src_path),
            "source_url": "",
            "added_date": "2026-10-13",
            "dir": f"{cat}\\{gid}",
            "thumb": f"{cat}/{gid}/thumb.png",
            "note": gdef["note"]
        }

        if gid in existing_gids:
            index = [entry if e["garment_id"] == gid else e for e in index]
        else:
            index.append(entry)
            existing_gids.add(gid)

        print(f"  [✓] 服装入库成功: {gdef['label']} ({cat}, 主色 {mean_hex}, 面积 {mask_area:,}px)")

    idx_file.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    import subprocess
    subprocess.run([sys.executable, str(ROOT / "tools" / "garment_extract" / "library_build_index.py")], check=True)
    print(f"  [✓] garment_library 索引回写完成！全库现有 {len(index)} 件服装。")


def ingest_combos():
    print("\n" + "=" * 65)
    print(">>> 3. Ingesting Lookbook Combo Matrix...")
    print("=" * 65)

    combos = [
        {
            "combo_id": "combo_lin_qingwan_mamianqun",
            "name": "林清婉 × 新中式织金马面裙套装",
            "char_id": "char_lin_qingwan",
            "garment_id": "full_20261013_02",
            "preview_image": "output/2026-10-13/characters/lin_qingwan/02_standalone_angles/char1_lin_qingwan_solo_01_front_9_16_124223_1.png",
            "preview_video": "",
            "prompt_preset": "Lin Qingwan wearing gold-threaded jacquard horse-face pleated skirt, standing gracefully in Chinese garden courtyard",
            "note": "新中式温婉角色与织金马面裙绝配搭配，端庄典雅，高契合度。",
            "tags": ["新中式", "马面裙", "温婉", "国风"],
            "added_date": "2026-10-13"
        },
        {
            "combo_id": "combo_jiang_yueyao_tailored_suit",
            "name": "姜月瑶 × 现代干练极简炭灰西装",
            "char_id": "char_jiang_yueyao",
            "garment_id": "full_20261013_01",
            "preview_image": "output/2026-10-13/characters/jiang_yueyao/02_standalone_angles/char2_jiang_yueyao_solo_01_front_9_16_124521_1.png",
            "preview_video": "",
            "prompt_preset": "Jiang Yueyao wearing tailored charcoal wool blazer suit, modern city streets background, chic fashion lookbook",
            "note": "灵动甜美角色反差穿搭炭灰西装，兼具干练与俏皮感。",
            "tags": ["都市", "西装", "干练", "混搭"],
            "added_date": "2026-10-13"
        },
        {
            "combo_id": "combo_ray_ling_tech_jacket",
            "name": "雷凌 × Y2K机能反光短夹克",
            "char_id": "char_ray_ling",
            "garment_id": "top_20261013_04",
            "preview_image": "output/2026-10-13/characters/ray_ling/01_ootd/char6_ray_ling_ootd_cyber_techwear_9_16_172221_1.png",
            "preview_video": "",
            "prompt_preset": "Ray Ling wearing Y2K cropped reflective technical jacket and tactical cargo pants, neon cityscape",
            "note": "银发赛博御姐与未来机能短夹克完美绑定，战术机能风格强烈。",
            "tags": ["赛博机能", "银发御姐", "反光夹克", "Y2K"],
            "added_date": "2026-10-13"
        },
        {
            "combo_id": "combo_qing_luo_silk_blouse",
            "name": "青洛 × 新中式黛绿真丝刺绣立领衫",
            "char_id": "char_qing_luo",
            "garment_id": "top_20261013_03",
            "preview_image": "output/2026-10-13/characters/qing_luo/01_ootd/char7_qing_luo_ootd_guofeng_ink_9_16_172508_1.png",
            "preview_video": "",
            "prompt_preset": "Qing Luo wearing celadon silk organza blouse with mandarin collar, misty bamboo grove background",
            "note": "水墨青花仙侠角色穿搭黛绿真丝轻纱，清幽出尘，诗情画意。",
            "tags": ["仙侠", "真丝立领衫", "青花水墨", "国风"],
            "added_date": "2026-10-13"
        },
        {
            "combo_id": "combo_shen_zhilan_cashmere_coat",
            "name": "沈知澜 × 经典驼色双面羊绒长大衣",
            "char_id": "char_shen_zhilan",
            "garment_id": "full_20261013_03",
            "preview_image": "output/2026-10-13/characters/shen_zhilan/01_ootd/char8_shen_zhilan_ootd_executive_power_9_16_172708_1.png",
            "preview_video": "",
            "prompt_preset": "Shen Zhilan wearing luxury camel double-faced cashmere trench coat, executive boardroom backdrop",
            "note": "律政投行大女主搭配双面羊绒长大衣，气场全开，老钱静奢标杆。",
            "tags": ["老钱风", "羊绒大衣", "大女主", "静奢"],
            "added_date": "2026-10-13"
        },
        {
            "combo_id": "combo_anya_punk_skirt_jacket",
            "name": "安雅 × 朋克苏格兰红黑格子百褶裙+皮夹克",
            "char_id": "char_anya_song",
            "garment_id": "btm_20261013_02",
            "preview_image": "output/2026-10-13/characters/anya_song/01_ootd/char9_anya_song_ootd_preppy_punk_9_16_173609_1.png",
            "preview_video": "",
            "prompt_preset": "Anya Song wearing red tartan pleated mini skirt and cropped leather biker jacket, cyber preppy look",
            "note": "千禧轻朋克少女与苏格兰格纹百褶裙、皮夹克天然合体，元气炸裂。",
            "tags": ["轻朋克", "格纹短裙", "皮夹克", "千禧学院"],
            "added_date": "2026-10-13"
        },
        {
            "combo_id": "combo_zhao_ruoxi_tennis_luxury",
            "name": "赵若溪 × 网球老钱风极简百褶裙运动套装",
            "char_id": "char_zhao_ruoxi",
            "garment_id": "full_20261013_06",
            "preview_image": "output/2026-10-13/characters/zhao_ruoxi/01_ootd/char4_zhao_ruoxi_ootd_quiet_luxury_9_16_140832_1.png",
            "preview_video": "",
            "prompt_preset": "Zhao Ruoxi wearing ivory tennis polo and knife-pleated skirt, private country club court",
            "note": "老钱静奢名媛与网球老钱运动套装，松弛感与精英格调兼备。",
            "tags": ["静奢", "网球风", "百褶裙", "名媛"],
            "added_date": "2026-10-13"
        },
        {
            "combo_id": "combo_chen_xiawei_french_dress",
            "name": "陈夏微 × 法式复古小碎花方领茶歇裙",
            "char_id": "char_chen_xiawei",
            "garment_id": "full_20261013_04",
            "preview_image": "output/2026-10-13/characters/chen_xiawei/01_ootd/char5_chen_xiawei_ootd_french_retro_9_16_140938_1.png",
            "preview_video": "",
            "prompt_preset": "Chen Xiawei wearing French romantic floral print silk tea dress, sunny Paris cafe balcony",
            "note": "法式复古女孩与碎花茶歇裙，浪漫唯美，微风吹拂柔美氛围。",
            "tags": ["法式复古", "茶歇裙", "碎花", "浪漫"],
            "added_date": "2026-10-13"
        }
    ]

    combos_file = ROOT / "combos.json"
    combos_file.write_text(json.dumps(combos, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [✓] Lookbook 搭配矩阵已写入 {combos_file} (共 {len(combos)} 套实测搭配)")


def sync_to_db():
    print("\n" + "=" * 65)
    print(">>> 4. Syncing SQLite Database (tools/asset_manager/assets.db)...")
    print("=" * 65)

    sys.path.insert(0, str(ROOT / "tools" / "asset_manager"))
    from backend.database import SessionLocal, init_db
    from backend.sync_engine import sync_all
    from backend.models import ComboModel

    init_db()
    db = SessionLocal()

    res = sync_all(db)
    print(f"  [✓] 基础同步完成: {res}")

    # Sync combos into database
    combos_file = ROOT / "combos.json"
    if combos_file.exists():
        combo_data = json.loads(combos_file.read_text(encoding="utf-8"))
        for item in combo_data:
            cid = item["combo_id"]
            model = db.query(ComboModel).filter_by(combo_id=cid).first()
            if not model:
                model = ComboModel(combo_id=cid)
                db.add(model)
            model.name = item.get("name", cid)
            model.char_id = item.get("char_id", "")
            model.garment_id = item.get("garment_id", "")
            model.preview_image = item.get("preview_image", "")
            model.preview_video = item.get("preview_video", "")
            model.prompt_preset = item.get("prompt_preset", "")
            model.note = item.get("note", "")
            model.tags_json = json.dumps(item.get("tags", []))
            model.added_date = item.get("added_date", "")
        db.commit()
        combo_count = db.query(ComboModel).count()
        print(f"  [✓] 搭配矩阵已同步入库: 共 {combo_count} 组绑定关系！")

    db.close()


if __name__ == "__main__":
    ingest_characters()
    ingest_garments()
    ingest_combos()
    sync_to_db()
    print("\n" + "=" * 65)
    print("🎉 全部资产入库完成！双击 start_asset_manager.bat 即可在浏览器即刻呈现！")
    print("=" * 65)

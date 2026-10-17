# -*- coding: utf-8 -*-
"""Hourly Scheduled Task: Random Standalone Garment Generator & Library Ingestion.

Workflow:
1. Generates a randomized garment item design following 'character-wardrobe-decoupling' standards.
2. Compiles a commercial ghost mannequin 9:16 prompt and executes Google Flow 0-credit image generation via CDP.
3. Automatically saves to output/YYYY-MM-DD/wardrobe/standalone_items/.
4. Generates CPU rembg transparent.png, white.png, thumb.png, and calculates dominant color mean_hex.
5. Ingests into garment_library/ (index.json, INDEX.md, index.html) and syncs into assets.db.
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
from PIL import Image
import numpy as np

# Set UTF-8 encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure execution in ComfyUI venv where dependencies (rembg, etc.) are installed
ROOT = Path(__file__).resolve().parent.parent
_venv_python = ROOT / "venv" / "Scripts" / "python.exe"
if _venv_python.exists() and Path(sys.executable).resolve() != _venv_python.resolve():
    sys.exit(subprocess.call([str(_venv_python)] + sys.argv))


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".agents" / "skills" / "google-flow-image" / "scripts"))
sys.path.insert(0, str(ROOT / "tools"))

from flow_unattended_worker import UnattendedFlowWorker
from asset_manager.backend.database import SessionLocal, init_db
from asset_manager.backend.sync_engine import sync_all

GARMENT_STYLES = [
    # Tops
    {
        "category": "tops",
        "prefix": "top",
        "label": "新中式黛绿半透真丝刺绣立领衫",
        "desc": "Neo-Chinese celadon silk organza blouse with mandarin collar and delicate bamboo embroidery",
        "prompt": "High-end fashion commercial product photography, vertical 9:16. A standalone Neo-Chinese celadon green semi-sheer silk organza blouse with mandarin collar, jade frog buttons, and delicate tone-on-tone embroidery, displayed on an invisible ghost mannequin against a pure solid white studio background. Exquisite translucent fabric drape, realistic silk luster, soft commercial studio lighting, ultra-detailed 8k resolution."
    },
    {
        "category": "tops",
        "prefix": "top",
        "label": "Y2K战术反光多口袋机能短夹克",
        "desc": "Y2K cropped tactical technical bomber jacket with modular utility pockets and 3M reflective trims",
        "prompt": "High-end commercial streetwear product photography, vertical 9:16. A standalone Y2K cropped tactical technical bomber jacket in matte gunmetal gray, featuring 3M reflective tape trims, modular utility pockets, and industrial matte black zippers, displayed on an invisible ghost mannequin against a pure solid white studio background. Crisp technical nylon fabric texture, realistic creases, studio lighting, 8k resolution."
    },
    {
        "category": "tops",
        "prefix": "top",
        "label": "法式复古方领微褶泡泡袖白衬衫",
        "desc": "French vintage ivory linen-silk square-neck blouse with subtle puff sleeves and shell buttons",
        "prompt": "High-end fashion commercial product photography, vertical 9:16. A standalone French romantic vintage blouse in ivory linen-silk blend, featuring an architectural square neckline, delicate micro-pleated puff sleeves, and mother-of-pearl buttons, displayed on an invisible ghost mannequin against a pure solid white studio background. Natural breathable fabric weave, soft studio lighting, 8k resolution."
    },
    {
        "category": "tops",
        "prefix": "top",
        "label": "极简燕麦色纯羊绒宽松高领针织衫",
        "desc": "Minimalist oatmeal pure cashmere relaxed turtleneck knit sweater with ribbed cuffs",
        "prompt": "Luxury knitwear commercial product photography, vertical 9:16. A standalone minimalist oatmeal-beige pure cashmere relaxed turtleneck sweater, featuring clean ribbed cuffs and hem, displayed on an invisible ghost mannequin against a pure solid white studio background. Supreme soft wool nap texture, natural cozy drape, soft commercial lighting, ultra-detailed 8k resolution."
    },
    # Bottoms
    {
        "category": "bottoms",
        "prefix": "btm",
        "label": "新中式改良织金织锦凤纹马面裙",
        "desc": "Neo-Chinese modern horse-face pleated skirt (mamianqun) with woven metallic gold phoenix patterns",
        "prompt": "High-end cultural fashion commercial photography, vertical 9:16. A standalone modern Neo-Chinese pleated horse-face skirt (mamianqun) in rich ink-black and woven metallic gold phoenix brocade, featuring crisp knife pleats and traditional wide waistband, displayed on an invisible ghost mannequin against a pure solid white studio background. Intricate jacquard texture, sharp geometric pleats, high fashion lighting, 8k resolution."
    },
    {
        "category": "bottoms",
        "prefix": "btm",
        "label": "朋克苏格兰红黑格纹刀褶双皮带百褶裙",
        "desc": "Punk tartan pleated mini skirt with dual black leather buckle straps and silver eyelets",
        "prompt": "High-end commercial streetwear photography, vertical 9:16. A standalone punk-inspired red and black tartan wool knife-pleated mini skirt, featuring dual black leather buckle belts with silver grommets and O-rings, displayed on an invisible ghost mannequin against a pure solid white studio background. Rich woolen plaid texture, realistic natural folds, crisp studio lighting, 8k resolution."
    },
    {
        "category": "bottoms",
        "prefix": "btm",
        "label": "老钱风垂坠象牙白高腰阔腿精纺西装裤",
        "desc": "Quiet luxury ivory pleated high-waisted wide-leg tailored wool trousers",
        "prompt": "Luxury tailoring commercial photography, vertical 9:16. A standalone pair of quiet-luxury ivory high-waisted wide-leg trousers in fine worsted wool, featuring front pleats and fluid drape, displayed on an invisible ghost mannequin against a pure solid white studio background. Impeccable tailoring, fluid wool crease, soft commercial lighting, 8k resolution."
    },
    # Full Outfits
    {
        "category": "full",
        "prefix": "full",
        "label": "高定午夜黑鱼骨丝绒开叉长礼服",
        "desc": "Haute couture midnight-black architectural plush velvet evening gown with corset boning and side slit",
        "prompt": "Haute couture commercial fashion product photography, vertical 9:16. A standalone midnight-black plush velvet strapless evening gown with architectural corset boning and an elegant high side slit, displayed on an invisible ghost mannequin against a pure solid white studio background. Rich deep velvet texture, luminous light reflections, high fashion studio lighting, 8k resolution."
    },
    {
        "category": "full",
        "prefix": "full",
        "label": "经典驼色双面手工羊绒系带大衣",
        "desc": "Classic camel double-faced hand-stitched cashmere wrap trench coat with self-tie belt",
        "prompt": "High-end luxury commercial fashion photography, vertical 9:16. A standalone classic double-faced camel cashmere wrap coat with relaxed notched lapels and self-tie sash belt, displayed on an invisible ghost mannequin against a pure solid white studio background. Supreme soft wool nap texture, natural fluid drape, high fashion studio lighting, ultra-detailed 8k resolution."
    },
    {
        "category": "full",
        "prefix": "full",
        "label": "法式复古小碎花方领泡泡袖真丝茶歇裙",
        "desc": "French romantic vintage ditsy floral print pastel silk midi tea dress with square neckline",
        "prompt": "High-end fashion commercial product photography, vertical 9:16. A standalone French romantic vintage midi tea dress in pastel cream with delicate ditsy floral print, featuring a square neckline, subtle puff shoulders, and mother-of-pearl buttons, displayed on an invisible ghost mannequin against a pure solid white studio background. Lightweight breathable silk crepe texture, romantic soft folds, clean commercial studio lighting, 8k resolution."
    },
    {
        "category": "full",
        "prefix": "full",
        "label": "老钱风网球极简百褶裙运动套装",
        "desc": "Quiet luxury ivory knit polo top and navy-striped knife-pleated mini tennis skirt ensemble",
        "prompt": "High-end luxury athleisure commercial photography, vertical 9:16. A standalone quiet-luxury tennis ensemble: crisp ivory knit polo collar sleeveless top paired with a sharp knife-pleated white mini tennis skirt with navy stripe accents, displayed on an invisible ghost mannequin against a pure solid white studio background. Premium pique knit texture, crisp pleat geometry, soft bright commercial studio lighting, 8k resolution."
    }
]

def generate_random_garments(count=1):
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    date_code = datetime.date.today().strftime("%Y%m%d")

    print("\n" + "=" * 65)
    print(f"【自动化服装生成任务启动】(目标数量: {count} 款)")
    print("=" * 65)

    # Execute generation via UnattendedFlowWorker
    worker = UnattendedFlowWorker()
    if not worker.connect():
        print("[!] 无法连接 Google Flow CDP 9222 端口，请确保 Chrome 已启动并开启 --remote-debugging-port=9222")
        return False

    from asset_dedup_generator import generate_unique_garment

    garment_lib = ROOT / "garment_library"
    idx_file = garment_lib / "index.json"
    index = json.loads(idx_file.read_text(encoding="utf-8")) if idx_file.exists() else []

    existing_labels = {g["label"].strip() for g in index}

    # Category balance check (tops, bottoms, full)
    cat_counts = {
        "tops": sum(1 for g in index if g.get("category") == "tops"),
        "bottoms": sum(1 for g in index if g.get("category") == "bottoms"),
        "full": sum(1 for g in index if g.get("category") == "full")
    }
    sorted_cats = sorted(["tops", "bottoms", "full"], key=lambda c: cat_counts.get(c, 0))

    chosen_styles = []
    for i in range(count):
        preferred_cat = sorted_cats[i % len(sorted_cats)]
        style = generate_unique_garment(existing_labels, category_preference=preferred_cat)
        chosen_styles.append(style)
        existing_labels.add(style["label"])

    from rembg import remove
    success_count = 0
    generated_garments = []

    try:
        for idx_i in range(count):
            gstyle = chosen_styles[idx_i]
            category = gstyle["category"]
            prefix = gstyle["prefix"]
            item_ts = datetime.datetime.now().strftime("%H%M%S")

            today_count = sum(1 for g in index if g["category"] == category and g["garment_id"].startswith(f"{prefix}_{date_code}"))
            seq = today_count + 1
            garment_id = f"{prefix}_{date_code}_{seq:02d}_{item_ts[:2]}"

            task_name = f"wardrobe_item_{garment_id}_9_16"
            print(f"\n--- [{idx_i + 1}/{count}] 服装生成: {gstyle['label']} ({category}) ---")
            print(f"  资产标识: {garment_id}")

            task = {
                "name": task_name,
                "character": gstyle["label"],
                "aspect": "9:16",
                "prompt": gstyle["prompt"]
            }

            saved_files = worker.execute_single_task(task, timeout_sec=150)
            if not saved_files:
                print(f"[!] 服装 {gstyle['label']} 生成超时或未捕获到成片，继续下一个...")
                continue

            gen_img_path = Path(saved_files[0])
            print(f"[✓] 图像生成成功并暂存至: {gen_img_path}")

            # Process and ingest into garment_library/<category>/<garment_id>/
            gdir = garment_lib / category / garment_id
            gdir.mkdir(parents=True, exist_ok=True)

            # 1. White PNG
            white_dst = gdir / "white.png"
            shutil.copy2(gen_img_path, white_dst)

            # 2. Transparent PNG via rembg
            raw_pil = Image.open(gen_img_path).convert("RGB")
            trans_dst = gdir / "transparent.png"
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
                "garment_id": garment_id,
                "category": category,
                "label": gstyle["label"],
                "mean_hex": mean_hex,
                "mask_area_px": mask_area,
                "crop_bbox": [0, 0, w, h],
                "size": [w, h],
                "method": "google_flow+rembg_cpu",
                "source_image": str(gen_img_path),
                "source_url": "",
                "added_date": today_str,
                "dir": f"{category}\\{garment_id}",
                "thumb": f"{category}/{garment_id}/thumb.png",
                "note": f"每小时自动化资产 · {gstyle['desc']}"
            }
            (gdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

            entry = {
                "garment_id": garment_id,
                "category": category,
                "label": gstyle["label"],
                "mean_hex": mean_hex,
                "mask_area_px": mask_area,
                "crop_bbox": [0, 0, w, h],
                "size": [w, h],
                "method": "google_flow+rembg_cpu",
                "source_image": str(gen_img_path),
                "source_url": "",
                "added_date": today_str,
                "dir": f"{category}\\{garment_id}",
                "thumb": f"{category}/{garment_id}/thumb.png",
                "note": f"每小时自动化资产 · {gstyle['desc']}"
            }

            index.append(entry)
            idx_file.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
            success_count += 1
            generated_garments.append(f"{gstyle['label']} ({garment_id})")
            print(f"[✓] 服装 {gstyle['label']} ({garment_id}) 入库成功")

    finally:
        worker.close()

    if success_count > 0:
        # Rebuild Markdown & HTML
        subprocess.run([sys.executable, str(ROOT / "tools" / "garment_extract" / "library_build_index.py")], check=True)

        # Sync SQLite
        init_db()
        db = SessionLocal()
        sync_all(db)
        db.close()

    print("\n" + "=" * 65)
    print(f"【批量服装生成完成】成功入库: {success_count}/{count} 款服装")
    for gg in generated_garments:
        print(f"  - {gg}")
    print("=" * 65)
    return success_count > 0

def generate_random_garment():
    """Backward compatibility alias for generating 1 garment."""
    return generate_random_garments(count=1)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Random Standalone Garment Generator")
    parser.add_argument("--count", type=int, default=1, help="Number of garments to generate (default: 1)")
    args = parser.parse_args()
    generate_random_garments(count=args.count)

# -*- coding: utf-8 -*-
"""Deduplicate existing character_library and garment_library assets.

Rules:
1. Group assets by unique identity:
   - For characters: base name (e.g. "洛晴川")
   - For garments: label + category (e.g. "Y2K战术反光多口袋机能短夹克" + "tops")
2. In each duplicate group, preserve the earliest/primary entry.
3. Move duplicate asset folders into output/archived_dupes/ for safety.
4. Update index.json, INDEX.md, index.html for both libraries.
5. Resync SQLite assets.db.
"""
import os
import sys
import json
import shutil
import datetime
from pathlib import Path
from collections import defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from char_lib_add import build_html as build_char_html, build_index_md as build_char_md
import subprocess
from asset_manager.backend.database import SessionLocal, init_db
from asset_manager.backend.models import CharacterModel, GarmentModel
from asset_manager.backend.sync_engine import sync_all

def dedup_characters():
    char_lib = ROOT / "character_library"
    idx_file = char_lib / "index.json"
    if not idx_file.exists():
        return 0

    index = json.loads(idx_file.read_text(encoding="utf-8"))
    archive_dir = ROOT / "output" / "archived_dupes" / "characters"
    archive_dir.mkdir(parents=True, exist_ok=True)

    seen_names = {}
    kept = []
    removed_ids = []

    for item in index:
        # Base name before parentheses
        raw_name = item.get("name", "")
        base_name = raw_name.split(" (")[0].strip()
        cid = item.get("char_id")

        if base_name in seen_names:
            print(f"[去重] 发现重复角色: {base_name} ({cid})，保留首版: {seen_names[base_name]}")
            removed_ids.append(cid)
            # Move folder
            char_folder = char_lib / "faces" / cid
            if char_folder.exists():
                dst = archive_dir / cid
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.move(str(char_folder), str(dst))
                print(f"  └─ 归档文件夹至: {dst}")
        else:
            seen_names[base_name] = cid
            kept.append(item)

    if removed_ids:
        idx_file.write_text(json.dumps(kept, ensure_ascii=False, indent=1), encoding="utf-8")
        build_char_html(kept)
        build_char_md(kept)
        print(f"[✓] 角色库去重完成: 移除 {len(removed_ids)} 个重复角色，保留 {len(kept)} 位独立角色")
    else:
        print("[✓] 角色库无重复角色")

    return len(removed_ids)

def dedup_garments():
    garment_lib = ROOT / "garment_library"
    idx_file = garment_lib / "index.json"
    if not idx_file.exists():
        return 0

    index = json.loads(idx_file.read_text(encoding="utf-8"))
    archive_dir = ROOT / "output" / "archived_dupes" / "garments"
    archive_dir.mkdir(parents=True, exist_ok=True)

    seen_keys = {}
    kept = []
    removed_ids = []

    for item in index:
        category = item.get("category", "")
        label = item.get("label", "").strip()
        gid = item.get("garment_id")

        # Identity key: category + label (ignore source id duplicates if categories differ)
        key = f"{category}::{label}"

        # If label is generic hash like "7686812393779123898_01", check if category differs
        if key in seen_keys:
            print(f"[去重] 发现重复服装: {label} [{category}] ({gid})，保留首版: {seen_keys[key]}")
            removed_ids.append(gid)
            # Move folder
            gdir = item.get("dir", "")
            if gdir:
                folder = garment_lib / gdir
                if folder.exists():
                    dst = archive_dir / Path(gdir).name
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.move(str(folder), str(dst))
                    print(f"  └─ 归档文件夹至: {dst}")
        else:
            seen_keys[key] = gid
            kept.append(item)

    if removed_ids:
        idx_file.write_text(json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8")
        subprocess.run([sys.executable, str(ROOT / "tools" / "garment_extract" / "library_build_index.py")], check=True)
        print(f"[✓] 服装库去重完成: 移除 {len(removed_ids)} 款重复服装，保留 {len(kept)} 款独立服装")
    else:
        print("[✓] 服装库无重复服装")

    return len(removed_ids)

def resync_database():
    init_db()
    db = SessionLocal()
    # Clean up DB deleted records
    char_lib = ROOT / "character_library" / "index.json"
    garment_lib = ROOT / "garment_library" / "index.json"
    char_ids = {c["char_id"] for c in json.loads(char_lib.read_text(encoding="utf-8"))} if char_lib.exists() else set()
    garment_ids = {g["garment_id"] for g in json.loads(garment_lib.read_text(encoding="utf-8"))} if garment_lib.exists() else set()

    # Delete stale chars
    db.query(CharacterModel).filter(~CharacterModel.char_id.in_(char_ids)).delete(synchronize_session=False)
    # Delete stale garments
    db.query(GarmentModel).filter(~GarmentModel.garment_id.in_(garment_ids)).delete(synchronize_session=False)
    db.commit()

    sync_all(db)
    db.close()
    print("[✓] SQLite 数据库已同步清理无冗余！")

def main():
    print("=" * 65)
    print("🧹 启动 AIGC 资产库去重清理程序")
    print("=" * 65)
    c_removed = dedup_characters()
    g_removed = dedup_garments()
    if c_removed > 0 or g_removed > 0:
        resync_database()
    print("=" * 65)
    print(f"✨ 去重清理完毕！角色库精简 -{c_removed}，服装库精简 -{g_removed}")
    print("=" * 65)

if __name__ == "__main__":
    main()

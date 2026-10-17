import sys
import json
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from asset_dedup_generator import generate_unique_garment, generate_unique_character

ROOT = Path(__file__).resolve().parent.parent

def test_dry_run():
    char_lib = ROOT / "character_library" / "index.json"
    garment_lib = ROOT / "garment_library" / "index.json"

    chars = json.loads(char_lib.read_text(encoding="utf-8")) if char_lib.exists() else []
    garments = json.loads(garment_lib.read_text(encoding="utf-8")) if garment_lib.exists() else []

    existing_cnames = {c["name"].split(" (")[0].strip() for c in chars}
    existing_glabels = {g["label"].strip() for g in garments}

    print("Existing characters:", len(existing_cnames))
    print("Existing garments:", len(existing_glabels))

    # Generate 20 candidate characters
    new_chars = []
    for _ in range(20):
        c = generate_unique_character(existing_cnames)
        assert c["cn_name"] not in existing_cnames, f"Duplicate char: {c['cn_name']}"
        existing_cnames.add(c["cn_name"])
        new_chars.append(c["cn_name"])

    # Generate 20 candidate garments
    new_garments = []
    for _ in range(20):
        g = generate_unique_garment(existing_glabels)
        assert g["label"] not in existing_glabels, f"Duplicate garment: {g['label']}"
        existing_glabels.add(g["label"])
        new_garments.append(f"[{g['category']}] {g['label']}")

    print("\n[✓] 成功模拟生成 20 位全新独立角色，零重名:")
    print("  ", ", ".join(new_chars[:10]), "...")
    print("\n[✓] 成功模拟生成 20 款全新独立服装，零重复:")
    for ng in new_garments[:5]:
        print("  -", ng)
    print("  ... 等 20 款")
    print("\n🎉 全部防重复与碰撞拦截测试 100% 验证通过！")

if __name__ == "__main__":
    test_dry_run()

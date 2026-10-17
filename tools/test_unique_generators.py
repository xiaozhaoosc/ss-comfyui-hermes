# -*- coding: utf-8 -*-
"""Test unique generation engines for characters and garments."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def test_dedup_integrity():
    char_lib = ROOT / "character_library" / "index.json"
    garment_lib = ROOT / "garment_library" / "index.json"

    chars = json.loads(char_lib.read_text(encoding="utf-8")) if char_lib.exists() else []
    garments = json.loads(garment_lib.read_text(encoding="utf-8")) if garment_lib.exists() else []

    char_names = [c["name"].split(" (")[0].strip() for c in chars]
    garment_labels = [f"{g['category']}::{g['label']}" for g in garments]

    from collections import Counter
    c_dupes = {k: v for k, v in Counter(char_names).items() if v > 1}
    g_dupes = {k: v for k, v in Counter(garment_labels).items() if v > 1}

    print(f"Current unique characters: {len(chars)}, Dupes: {c_dupes}")
    print(f"Current unique garments: {len(garments)}, Dupes: {g_dupes}")
    assert len(c_dupes) == 0, f"Character dupes exist: {c_dupes}"
    assert len(g_dupes) == 0, f"Garment dupes exist: {g_dupes}"
    print("ALL INTEGRITY CHECKS PASSED: ZERO DUPLICATES!")

if __name__ == "__main__":
    test_dedup_integrity()

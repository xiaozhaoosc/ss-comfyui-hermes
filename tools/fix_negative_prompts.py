#!/usr/bin/env python3
"""修复负面词：删除被误加的「不要缎面材质实色」等反噬短语"""

import json, os, re, shutil

PROMPT_DIR = r"D:\obsidian\obsidian\ComfyUI\50写真批次prompts"

# 需要清理的负面词短语（按长度从长到短）
NEG_RULES = [
    ("，不要缎面材质实色", ""),
    (",不要缎面材质实色", ""),
    ("不要缎面材质实色，", ""),
    ("不要缎面材质实色,", ""),
    ("不要缎面材质实色", ""),
]

def clean_negative(text):
    n = 0
    for old, new in NEG_RULES:
        if old in text:
            text = text.replace(old, new)
            n += 1
    # 清理多余逗号
    text = re.sub(r'，{2,}', '，', text)
    text = re.sub(r', {2,}', ', ', text)
    text = re.sub(r'^[，,]+', '', text)
    text = re.sub(r'[，,]+$', '', text)
    return text, n

def main():
    total = 0
    for fn in sorted(os.listdir(PROMPT_DIR)):
        if not re.match(r'batch\d+_.*\.json$', fn): continue
        src = os.path.join(PROMPT_DIR, fn)
        data = json.load(open(src, encoding='utf-8'))
        if not isinstance(data, list): continue
        changed = 0
        for p in data:
            p['negative'], n = clean_negative(p.get('negative', ''))
            changed += n
        json.dump(data, open(src, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f"{fn}: 清理 {changed} 处")
        total += changed
    print(f"\n合计清理 {total} 处")

if __name__ == '__main__':
    main()

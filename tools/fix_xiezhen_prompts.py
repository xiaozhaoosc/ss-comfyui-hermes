#!/usr/bin/env python3
"""写真提示词修复：删除/替换 透明/略透/薄纱/透视/走光 措辞 → 实色材质

修复对象：D:/obsidian/obsidian/ComfyUI/50写真批次prompts/batch*.json (6批×50=300条)
- 备份原文件到 backup_original/
- 替换规则（保留其余全部内容与 seed 逻辑）：
  透明吊带 → 缎面吊带 / 透明 → 缎面
  略透 → 实色 / 薄纱 → 缎面 / 透视 → 实色
  「透视纱裙下人腿部呈双平行走光」→「纱裙修饰腿部线条」
  半透 → 实色 / 若隐若现 → 清晰可见 / 走光 → 修饰线条
输出：修改统计 + 替换日志 D:/obsidian/obsidian/ComfyUI/50写真批次prompts/fix_log.txt
"""
import json, os, re, shutil, datetime

PROMPT_DIR = r"D:\obsidian\obsidian\ComfyUI\50写真批次prompts"
BACKUP_DIR = os.path.join(PROMPT_DIR, "backup_original")
LOG = os.path.join(PROMPT_DIR, "fix_log.txt")

# 替换规则：旧短语 → 新短语（按长度从长到短，避免短词误伤）
RULES = [
    ("透视纱裙下人腿部呈双平行走光", "纱裙裙摆修饰腿部线条"),
    ("透明吊带比基尼", "缎面吊带比基尼"),
    ("透明吊带", "缎面吊带"),
    ("略透", "实色"),
    ("半透", "实色"),
    ("透明薄纱", "缎面材质"),
    ("透明", "缎面"),
    ("薄纱", "缎面"),
    ("透视", "实色"),
    ("若隐若现", "清晰可辨"),
    ("走光", "线条修饰"),
]

def fix_text(text):
    n = 0
    for old, new in RULES:
        c = text.count(old)
        if c:
            text = text.replace(old, new)
            n += c
            log_lines.append(f"  '{old}' → '{new}' x{c}")
    return text, n

def main():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    log_lines.append(f"=== 修复执行 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} ===")
    total = 0
    files = [f for f in sorted(os.listdir(PROMPT_DIR)) if re.match(r'batch\d+_.*\.json$', f)]
    for fn in files:
        src = os.path.join(PROMPT_DIR, fn)
        data = json.load(open(src, encoding='utf-8'))
        if not isinstance(data, list):
            log_lines.append(f"SKIP {fn} (非列表)")
            continue
        # 备份（只备份一次）
        bak = os.path.join(BACKUP_DIR, fn)
        if not os.path.exists(bak):
            shutil.copy2(src, bak)
        changed = 0
        for p in data:
            p['positive'], n = fix_text(p.get('positive', ''))
            changed += n
            p['negative'], n2 = fix_text(p.get('negative', ''))
            changed += n2
        json.dump(data, open(src, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        log_lines.append(f"{fn}: 替换 {changed} 处")
        total += changed
    log_lines.append(f"=== 合计替换 {total} 处 → 备份在 backup_original/ ===")
    with open(LOG, 'w', encoding='utf-8') as f:
        f.write("\n".join(log_lines))
    print("\n".join(log_lines))

log_lines = []
if __name__ == '__main__':
    main()

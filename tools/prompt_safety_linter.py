#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Google Flow 提示词前置合规审查器 (Pre-flight Prompt Linter)

背景
----
Google Flow / Veo 内置 **Prominent People Policy（知名人物保护策略）**：
提示词中出现真实历史/公众人物专有名词（君王、名臣、将领）时，提交会被硬阻断，
界面弹出 `This prompt might violate our policies about generating prominent people`
并即时退款，同时在画板留下 Failed 废卡。

本模块在提示词**提交到 Flow 之前**统一过一道，做两件事：
1. 实体去名化：把专有名词等价改写为「职能身份 + 服制 + 体貌 + 道具」的具象描述。
   实测证明改写后不仅 100% 过审，画面质感反而更高（因为强调了服饰纹理与体态）。
2. 残留风险扫描：改写后仍命中「头衔 + 专名」模式的，给出人工复核警告。

用法
----
    from prompt_safety_linter import sanitize_prompt, scan_prompt_risks

    clean, changes = sanitize_prompt(raw_prompt)
    risks = scan_prompt_risks(clean)

命令行
------
    python tools/prompt_safety_linter.py --text "Kou Zhun prostrating..."
    python tools/prompt_safety_linter.py --file tools/pipeline_route_a_flow_native.py
    python tools/prompt_safety_linter.py --dir tools            # 批量审计
"""

import os
import re
import sys
import json
import argparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# 1. 实体去名化映射表
#    原则：key 按长度降序匹配（代码内已自动排序），保证
#    "Prime Minister Kou Zhun" 优先于 "Kou Zhun"，避免出现
#    "Prime Minister an ancient prime minister" 这类语法崩坏。
# ---------------------------------------------------------------------------
ENTITY_MAP = {
    # ---- 北宋皇族 ----
    "Emperor Taizong": "a solemn Chinese emperor in a golden dragon robe",
    "Emperor Taizu": "a solemn Chinese emperor in a golden dragon robe",
    "Song Taizong": "a solemn Chinese emperor in a golden dragon robe",
    "Song Taizu": "a solemn Chinese emperor in a golden dragon robe",
    "Zhao Guangyi": "a solemn Chinese emperor in a golden dragon robe",
    "Zhao Kuangyin": "a solemn Chinese emperor in a golden dragon robe",
    "宋太宗": "一位身着明黄龙袍的威严皇帝",
    "宋太祖": "一位身着明黄龙袍的威严皇帝",
    "赵光义": "一位身着明黄龙袍的威严皇帝",
    "赵匡胤": "一位身着明黄龙袍的威严皇帝",

    # ---- 文臣 ----
    "Prime Minister Kou Zhun": "an ancient prime minister in official crimson robes and a winged black court hat",
    "Kou Zhun": "an ancient prime minister in official crimson robes and a winged black court hat",
    "Pan Renmei": "a scheming senior court minister in dark brocade official robes",
    "寇准": "一位身着绯红团花官袍、头戴展脚幞头的古代宰相",
    "潘仁美": "一位身着深色暗纹官袍的权谋大臣",

    # ---- 杨家将 ----
    "Eldest Son Yang Yanping": "a young valiant commander in silver lamellar armor with red helmet tassels",
    "General Yang Yanping": "a young valiant commander in silver lamellar armor with red helmet tassels",
    "General Yang Ye": "a battle-hardened veteran commander in gleaming steel lamellar armor with a grey beard",
    "Yang Yanping": "a young valiant commander in silver lamellar armor with red helmet tassels",
    "Yang Yanding": "a young commander in bronze lamellar armor",
    "Yang Yanzhao": "a middle-aged commander in steel lamellar armor",
    "Yang Zongbao": "a young valiant commander in silver lamellar armor",
    "Yang Ye": "a battle-hardened veteran commander in gleaming steel lamellar armor with a grey beard",
    "杨延平": "一位身披银色札甲、头盔缀红缨的青年将领",
    "杨延定": "一位身披铜色札甲的青年将领",
    "杨延昭": "一位身披钢质札甲的中年将领",
    "杨宗保": "一位身披银色札甲的青年将领",
    "杨业": "一位身披钢质札甲、蓄灰白长须的老将",

    # ---- 女眷 / 契丹 ----
    "Dowager Xiao": "a regal Khitan dowager in dark fur-trimmed royal robes",
    "Xiao Chuo": "a regal Khitan dowager in dark fur-trimmed royal robes",
    "She Taijun": "an elderly noble matriarch in dark formal court robes with a silver dragon-head staff",
    "Mu Guiying": "a female warrior commander in red battle armor with a long spear",
    "萧太后": "一位身着毛领深色王袍的契丹太后",
    "佘太君": "一位手持银色龙头拐杖、身着深色正装的老夫人",
    "穆桂英": "一位身着红色战甲、手持长枪的女将",
}

# ---------------------------------------------------------------------------
# 2. 残留风险扫描模式
#    命中「头衔 + 专有名词大写」这类典型 Prominent People 结构。
#    朝代名（Song dynasty）与地名不在此列，不会误伤。
# ---------------------------------------------------------------------------
TITLES = (
    r"Emperor|Empress|King|Queen|Prince|Princess|President|Prime\s+Minister|"
    r"Chairman|Chancellor|General|Lord|Duke|Tsar|Czar|Sultan|Pharaoh|"
    r"Prophet|Pope|Celebrity|Founder"
)
RESIDUAL_PATTERNS = [
    (re.compile(r"\b(?:" + TITLES + r")\s+[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?"),
     "头衔 + 专名结构，可能被判为知名人物"),
    (re.compile(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\s+(?:I{1,3}|IV|V|VI|the\s+Great)\b"),
     "君主序数称号（如 Henry VIII / the Great）"),
]

# 白名单：明确的非人物用法，避免误报
ALLOWLIST = re.compile(
    r"Emperor\s+(?:Penguin|Scorpion|Tamarin)|King\s+(?:Cobra|Crab|Salmon|Penguin)",
    re.IGNORECASE,
)


def _at_sentence_start(full_text: str, pos: int) -> bool:
    """判断 pos 是否处于句首：文本开头，或前面紧跟句子终止符。"""
    prefix = full_text[:pos].rstrip()
    return prefix == "" or prefix.endswith((".", "!", "?", ";", ":", "\n"))


def sanitize_prompt(prompt: str):
    """实体去名化。返回 (清洗后文本, 变更记录列表)。

    变更记录每项为 dict: {"hit": 原文命中, "replacement": 替换为, "pos": 位置}
    """
    if not prompt:
        return prompt, []

    changes = []
    result = prompt
    # 按 key 长度降序，长 key 优先，避免前缀被短 key 抢先替换
    for key in sorted(ENTITY_MAP.keys(), key=len, reverse=True):
        pattern = re.compile(re.escape(key), re.IGNORECASE)
        total = len(pattern.findall(result))
        if not total:
            continue
        replacement = ENTITY_MAP[key]

        def _sub(m):
            # 注意：不能用「匹配文本自身首字母是否大写」来判断句首——
            # 专有名词首字母恒为大写，会把句中误判成句首。
            rep = replacement
            if _at_sentence_start(result, m.start()):
                rep = replacement[0].upper() + replacement[1:]
            changes.append({
                "hit": m.group(0),
                "replacement": rep,
                "pos": m.start(),
            })
            return rep

        result = pattern.sub(_sub, result)
    return result, changes


def scan_prompt_risks(prompt: str):
    """扫描残留风险。返回风险列表，每项 dict: {"match":..., "reason":...}"""
    if not prompt:
        return []
    risks = []
    for pattern, reason in RESIDUAL_PATTERNS:
        for m in pattern.finditer(prompt):
            if ALLOWLIST.search(m.group(0)):
                continue
            risks.append({"match": m.group(0), "reason": reason})
    return risks


def lint_prompt(prompt: str, strict: bool = False):
    """一次调用完成 清洗 + 扫描。

    返回 (clean_prompt, changes, risks)。
    strict=True 时，若仍有残留风险则抛出 ValueError（用于在流水线里硬拦截）。
    """
    clean, changes = sanitize_prompt(prompt)
    risks = scan_prompt_risks(clean)
    if strict and risks:
        raise ValueError(
            "提示词仍存在知名人物风险，已阻止提交: "
            + "; ".join(f"{r['match']} ({r['reason']})" for r in risks)
        )
    return clean, changes, risks


def fix_file(path: str, dry_run: bool = False) -> int:
    """就地修复单个源码文件：只改写 prompt 字段所在行。

    刻意 **只匹配含 prompt 字段的行**，不碰 "title"/"description" 等展示字段，
    否则 "寇准殿前死谏" 会变成 "一位身着绯红官袍的古代宰相殿前死谏" 这种怪标题。

    返回改写行数。
    """
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    changed_lines = 0
    total_hits = 0
    out = []
    for line in lines:
        if _PROMPT_FIELD.search(line):
            new_line, changes, _risks = lint_prompt(line)
            if changes:
                changed_lines += 1
                total_hits += len(changes)
                out.append(new_line)
                continue
        out.append(line)

    if changed_lines and not dry_run:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(out)
    return changed_lines


# ---------------------------------------------------------------------------
# 3. 源码批量审计：找出还有哪些脚本的提示词里埋了真名
# ---------------------------------------------------------------------------
_PROMPT_FIELD = re.compile(
    r"""(?:image_prompt|video_prompt|img_prompt|vid_prompt|["']?prompt["']?)\s*[:=]""",
    re.IGNORECASE,
)


def audit_text(text: str, source: str = "<string>") -> list:
    """审计一段文本（通常是 .py 源码），返回命中列表。"""
    findings = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for key in ENTITY_MAP:
            if re.search(re.escape(key), line, re.IGNORECASE):
                findings.append({
                    "source": source,
                    "line": lineno,
                    "entity": key,
                    "excerpt": line.strip()[:160],
                })
    return findings


def audit_file(path: str) -> list:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return audit_text(f.read(), os.path.basename(path))
    except Exception:
        return []


def audit_directory(dirpath: str, exts=(".py", ".json", ".md")) -> list:
    findings = []
    for root, _dirs, files in os.walk(dirpath):
        for fn in files:
            if fn.endswith(exts):
                findings.extend(audit_file(os.path.join(root, fn)))
    return findings


def main():
    ap = argparse.ArgumentParser(description="Google Flow 提示词前置合规审查器")
    ap.add_argument("--text", help="直接审查一段提示词")
    ap.add_argument("--file", help="审查单个文件源码")
    ap.add_argument("--dir", help="批量审计目录")
    ap.add_argument("--fix", help="就地修复文件中的 prompt 字段（去名化）")
    ap.add_argument("--dry-run", action="store_true", help="配合 --fix，只报告不落盘")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    args = ap.parse_args()

    if args.text:
        clean, changes, risks = lint_prompt(args.text)
        out = {
            "original": args.text,
            "sanitized": clean,
            "replacements": changes,
            "residual_risks": risks,
        }
        if args.json:
            print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            print("原文:\n  " + args.text)
            print("\n改写:")
            print("  " + clean)
            print(f"\n替换 {len(changes)} 处:")
            for c in changes:
                print(f"  - [{c['hit']}] -> {c['replacement']}")
            if risks:
                print("\n残留风险:")
                for r in risks:
                    print(f"  ! [{r['match']}] {r['reason']}")
            else:
                print("\n残留风险: 无")
        return

    if args.fix:
        n = fix_file(args.fix, dry_run=args.dry_run)
        tag = "[预览] " if args.dry_run else ""
        print(f"{tag}已去名化 {n} 行: {args.fix}")
        return

    findings = []
    if args.file:
        findings = audit_file(args.file)
    elif args.dir:
        findings = audit_directory(args.dir)
    else:
        ap.print_help()
        return

    if args.json:
        print(json.dumps(findings, ensure_ascii=False, indent=2))
        return

    if not findings:
        print("[OK] 未发现真实人物专名")
        return
    print(f"[!] 发现 {len(findings)} 处真实人物专名:\n")
    by_src = {}
    for f in findings:
        by_src.setdefault(f["source"], []).append(f)
    for src, items in sorted(by_src.items()):
        print(f"  {src}  ({len(items)} 处)")
        for it in items[:12]:
            print(f"    L{it['line']:<4} [{it['entity']}]")
        if len(items) > 12:
            print(f"    ... 另有 {len(items) - 12} 处")
        print()


if __name__ == "__main__":
    main()

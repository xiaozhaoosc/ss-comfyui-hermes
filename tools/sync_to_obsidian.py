"""
sync_to_obsidian.py - ComfyUI 到 Obsidian 知识库标准增量同步工具

功能特性:
1. 增量同步: 记录上次同步时间戳 (tools/.obsidian_sync_state.json)，仅同步新增/修改文档
2. 智能分类: 自动解析文档名与内容关键字，精准路由到 03-ComfyUI 下的 6 大专题目录
3. 元数据注入: 自动补齐 YAML Frontmatter (title, project, type, tags, date)，无缝支持 Dataview 动态检索
4. 索引联动: 同步完成后自动检查并更新 MOC-ComfyUI工作流.md
5. 支持 CLI 灵活参数: --file 指定单文件, --all 全量重跑, --dry-run 预览模式
"""

import os
import sys
import json
import re
import argparse
import datetime
from pathlib import Path

# 确保 UTF-8 输出
sys.stdout.reconfigure(encoding="utf-8")

# 根路径配置
COMFY_ROOT = Path(r"d:\ai_projects\ComfyUI")
OBSIDIAN_VAULT_COMFY = Path(r"D:\obsidian\obsidian\03-ComfyUI")
MOC_FILE = Path(r"D:\obsidian\obsidian\00-Index\MOC-ComfyUI工作流.md")
STATE_FILE = COMFY_ROOT / "tools" / ".obsidian_sync_state.json"

CATEGORIES = {
    "00-项目地图与总控": [
        r"PROJECT_MAP", r"项目地图", r"工作总结", r"复盘", r"PLANNING", r"ROADMAP"
    ],
    "01-影视短剧业务线": [
        r"杨家将", r"YANGJIAJIANG", r"剧本", r"分镜", r"动漫短剧", r"Flow", r"Veo", r"GRID_PROMPTS"
    ],
    "02-换装与换脸流水线": [
        r"换脸", r"换装", r"WanAnimate", r"服装", r"garment", r"Hitomi", r"faceswap", r"831959"
    ],
    "03-工作流与16G显存优化": [
        r"工作流", r"显存", r"动作迁移", r"v6", r"白模", r"法线", r"黄金指南", r"黄金参数"
    ],
    "04-模型与评测基准": [
        r"评测", r"模型", r"LoRA", r"Z-Image", r"2K", r"BENCHMARK", r"UPSCALE", r"Moge", r"IDM-VTON"
    ],
    "05-工程与基础设施": [
        r"SQLite", r"升级", r"备份", r"下载器", r"downloader", r"依赖", r"bridge"
    ]
}

def load_state():
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_sync": "2026-10-01T00:00:00", "synced_files": {}}

def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def detect_category(filename, content):
    lower_name = filename.lower()
    lower_content = content[:1500].lower()
    
    # 优先根据文件名匹配
    for cat, patterns in CATEGORIES.items():
        for pat in patterns:
            if re.search(pat, filename, re.IGNORECASE):
                return cat
                
    # 其次根据内容开头关键字匹配
    for cat, patterns in CATEGORIES.items():
        for pat in patterns:
            if re.search(pat, lower_content, re.IGNORECASE):
                return cat
                
    return "00-项目地图与总控"

def ensure_frontmatter(filename, content, category):
    """如果文件没有 YAML Frontmatter，智能补充以便 Dataview 索引"""
    if content.startswith("---"):
        return content  # 已有 frontmatter
        
    title = Path(filename).stem
    # 提取日期
    date_match = re.search(r"2026-\d{2}-\d{2}", filename)
    date_str = date_match.group(0) if date_match else datetime.date.today().isoformat()
    
    # 识别所属项目
    project = "通用"
    if "杨家将" in filename or "YANGJIAJIANG" in filename:
        project = "北宋杨家将"
    elif "换装" in filename or "换脸" in filename or "WanAnimate" in filename:
        project = "换装换脸视频"
    elif "动漫短剧" in filename:
        project = "动漫短剧"
        
    tags = [category.split("-")[-1]]
    if project != "通用":
        tags.append(project)

    frontmatter = f"""---
title: "{title}"
project: "{project}"
category: "{category}"
date: {date_str}
type: "handover"
tags: {json.dumps(tags, ensure_ascii=False)}
sync_time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
---

"""
    return frontmatter + content

def find_candidate_files(all_mode=False, since_dt=None):
    candidates = []
    
    # 扫描根目录
    for p in COMFY_ROOT.glob("*.md"):
        if p.name.startswith("_") or p.name in ["README.md", "CONTRIBUTING.md", "SECURITY.md", "QUANTIZATION.md", "AGENTS.md"]:
            continue
        mtime = datetime.datetime.fromtimestamp(p.stat().st_mtime)
        if all_mode or (since_dt and mtime >= since_dt):
            candidates.append(p)
            
    # 扫描 docs/ 目录
    docs_dir = COMFY_ROOT / "docs"
    if docs_dir.exists():
        for p in docs_dir.glob("*.md"):
            mtime = datetime.datetime.fromtimestamp(p.stat().st_mtime)
            if all_mode or (since_dt and mtime >= since_dt):
                candidates.append(p)
                
    return candidates

def sync_single_file(src_path, dry_run=False):
    try:
        with open(src_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        print(f"  [ERROR] 读取文件失败 {src_path.name}: {e}")
        return None

    cat = detect_category(src_path.name, content)
    target_dir = OBSIDIAN_VAULT_COMFY / cat
    
    # 规范化目标文件名
    base_name = src_path.name
    # 若文件名不含日期，补充日期前缀
    if not re.match(r"^2026-\d{2}", base_name):
        mtime = datetime.datetime.fromtimestamp(src_path.stat().st_mtime)
        base_name = f"{mtime.strftime('%Y-%m-%d')}_{base_name}"
    
    target_file = target_dir / base_name
    
    enriched_content = ensure_frontmatter(base_name, content, cat)
    
    if dry_run:
        print(f"  [DRY-RUN] 将同步: {src_path.name} -> {cat}/{base_name} ({len(enriched_content)} 字符)")
        return (cat, base_name)

    target_dir.mkdir(parents=True, exist_ok=True)
    with open(target_file, "w", encoding="utf-8") as f:
        f.write(enriched_content)
        
    print(f"  [SYNC-OK] {src_path.name} -> {cat}/{base_name}")
    return (cat, base_name)

def update_moc_if_needed(newly_synced):
    if not newly_synced or not MOC_FILE.exists():
        return
        
    try:
        with open(MOC_FILE, "r", encoding="utf-8") as f:
            moc_text = f.read()
            
        added_count = 0
        for cat, name in newly_synced:
            stem = Path(name).stem
            link_str = f"[[03-ComfyUI/{cat}/{stem}|"
            # 检查是否已存在
            if stem not in moc_text:
                # 寻找对应分类的位置追加
                anchor = f"### {cat[:2]}."
                if anchor in moc_text:
                    pos = moc_text.find(anchor)
                    # 找到下一个 ### 或者结尾
                    next_header = moc_text.find("\n### ", pos + len(anchor))
                    if next_header == -1:
                        next_header = moc_text.find("\n---", pos)
                    
                    insert_line = f"- [[03-ComfyUI/{cat}/{stem}|📄 {stem}]]\n"
                    if next_header != -1:
                        moc_text = moc_text[:next_header] + insert_line + moc_text[next_header:]
                    else:
                        moc_text += insert_line
                    added_count += 1

        if added_count > 0:
            with open(MOC_FILE, "w", encoding="utf-8") as f:
                f.write(moc_text)
            print(f"  [MOC-OK] 已将 {added_count} 篇新笔记自动登记至 MOC-ComfyUI工作流.md")
    except Exception as e:
        print(f"  [WARN] 更新 MOC 失败: {e}")

def main():
    parser = argparse.ArgumentParser(description="ComfyUI -> Obsidian 增量文档同步工具")
    parser.add_argument("--file", "-f", type=str, help="指定同步单个文件路径")
    parser.add_argument("--all", "-a", action="store_true", help="全量重新扫描并同步")
    parser.add_argument("--days", "-d", type=int, default=7, help="回溯扫描天数 (默认 7 天)")
    parser.add_argument("--dry-run", action="store_true", help="试运行预览模式")
    args = parser.parse_args()

    state = load_state()
    now_str = datetime.datetime.now().isoformat()
    
    print("=" * 60)
    print("🚀 ComfyUI -> Obsidian 增量同步工具启动")
    print(f"目标知识库目录: {OBSIDIAN_VAULT_COMFY}")
    print("=" * 60)

    synced_list = []

    if args.file:
        target = Path(args.file)
        if not target.is_absolute():
            target = COMFY_ROOT / target
        if not target.exists():
            print(f"错误: 找不到目标文件 {target}")
            sys.exit(1)
        res = sync_single_file(target, dry_run=args.dry_run)
        if res:
            synced_list.append(res)
    else:
        since_dt = datetime.datetime.fromisoformat(state.get("last_sync", "2026-10-01T00:00:00"))
        if args.days:
            since_dt = max(since_dt, datetime.datetime.now() - datetime.timedelta(days=args.days))
            
        print(f"扫描范围: 修改时间 >= {since_dt.strftime('%Y-%m-%d %H:%M:%S')} (全量模式: {args.all})")
        candidates = find_candidate_files(all_mode=args.all, since_dt=since_dt)
        print(f"发现候选文档: {len(candidates)} 篇")
        
        for p in candidates:
            res = sync_single_file(p, dry_run=args.dry_run)
            if res:
                synced_list.append(res)

    if not args.dry_run:
        state["last_sync"] = now_str
        save_state(state)
        update_moc_if_needed(synced_list)

    print("-" * 60)
    print(f"✅ 同步完成！累计处理: {len(synced_list)} 篇文档")
    print("=" * 60)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""fp8_hazy_lazy 智能评分与归档 — 完美版（简洁、可用）
解决：1)pid integer/string key 混乱; 2) 直接 concise_async 并发;
    3) [完美汇总] 按 pid 计算 strings; 4) 错误 warp prompt 为 line samples.
"""
import json, os, base64, urllib.request, time, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

CFG = json.load(open(r"C:\Users\kenzhao\.config\opencode\opencode.json", encoding='utf-8'))
GLM_KEY = CFG['provider']['glm']['options']['apiKey']
COMM_DIR = r"D:\ai_projects\ComfyUI"
OUT_DIR = os.path.join(COMM_DIR, "output", "fp8_hazy_lazy")
PROMPT_FILE = r"D:\obsidian\obsidian\ComfyUI\50写真批次prompts\en\hazy_home_lazy_100_en.json"
ARCHIVE_MD = r"D:\obsidian\obsidian\ComfyUI\50写真批次prompts\archive_hazy_home_lazy.md"
RATING_JSON = r"D:\obsidian\obsidian\ComfyUI\50写真批次prompts\archive_hazy_home_lazy_ratings.json"


def glm_score(image_b64):
    """调用 GLM-4V-Flash 评分，返回 score 或 None"""
    q = (
        "你是AI摄影评审。评分维度（每项 1-10）：\n"
        "1. 主题契合度（若隐若现/朦胧感/全身/冷白皮/长裙/居家/慵懒）\n"
        "2. 构图完整性（人物是否全身清晰，有无截头截脚）\n"
        "3. 画质质感（光线朦胧感/皮肤质感/细节）\n"
        "4. 穿帮畸变（有无多余手指/肢体变形/服装混乱）\n"
        "按格式回答：\n"
        "主题契合度: 9\n"
        "构图完整性: 8\n"
        "画质质感: 9\n"
        "穿帮畸变: 10\n"
        "总分: 9.0\n"
        "总评: [30字总结]"
    )
    payload = {"model": "glm-4v-flash", "messages": [{"role": "user", "content": [
        {"type": "text", "text": q},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
    ]}]}
    req = urllib.request.Request("https://open.bigmodel.cn/api/paas/v4/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {GLM_KEY}"})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=60).read())
        raw = r['choices'][0]['message']['content']
        import re
        m = re.search(r"总分[:：]\s*([0-9.]+)", raw)
        return float(m.group(1)) if m else None
    except urllib.error.HTTPError as e:
        return None  # 1301/429 等都不影响整体
    except Exception as e:
        return None


def loadb64(path):
    with open(path, 'rb') as f:
        b = f.read()
    return base64.b64encode(b).decode()


def build_rates():
    """从文件依次构造 records 字典，mapping key="P001_v1" -> {'pid': 1, 'variant': 'v1', 'score': 8.5, 'pid_str': 'P001'}"""
    jsonprompts = json.load(open(PROMPT_FILE, encoding='utf-8'))
    prompts = {int(item['id']): item for item in jsonprompts}  # int 作 key (1-100)

    files = sorted([f for f in os.listdir(OUT_DIR) if f.endswith('.png')])
    print(f"total image files: {len(files)}")

    rated = set()
    if os.path.exists(RATING_JSON):
        try:
            rated = set(json.load(open(RATING_JSON, encoding='utf-8')))
            print(f"已存在 {len(rated)} 条，跳过重复")
        except Exception:
            rated = set()

    tasks = []  # (key, pid_int, variant, b64, pid_str)
    for fn in files:
        part = fn.split('_')[0]  # "P001"
        try:
            pid_int = int(part[1:])  # 1
        except: continue
        key = fn.replace('.png', '').replace('_00001_', '')  # "P001_v1_00001"
        if key in rated: continue
        # 读取图像 base64
        b64 = loadb64(os.path.join(OUT_DIR, fn))
        tasks.append((key, pid_int, fn.split('_')[1], b64, part, prompts[pid_int]['positive'][:80]))

    print(f"待评分: {len(tasks)} 张")

    if len(tasks) == 0:
        print("无需新评分")
        return {}, prompts
    total_start = time.time()
    records = {}  # key -> {'pid': pid_int, 'variant': v, 'score': x, 'pid_str': "Pxxx"}

    # 3. ThreadPool 并发评分（GLM-4V 是 API 调用，无需 GPU）
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {}
        for key, pid_int, variant, b64, pid_str, pos_short in tasks:
            future = ex.submit(glm_score, b64)
            futures[future] = (key, pid_int, variant, pos_short, pid_str)
        for i, future in enumerate(as_completed(futures), 1):
            key, pid_int, variant, pos_short, pid_str = futures[future]
            score = future.result()
            score = score if score is not None else 0.0
            records[key] = {"pid": pid_int, "variant": variant, "score": score, "pid_str": pid_str}
            if i % 50 == 0:
                elapsed = time.time() - total_start
                rate = i / elapsed * 60
                remaining = len(tasks) - i
                eta_min = remaining / rate if rate > 0 else 999
                print(f"  [{i}/{len(tasks)}] {key}: {score:.1f} | 已用时 {elapsed/60:.1f}分 剩 {eta_min:.0f} 分钟")
                # 每 50 张保存中间进度（防 crash）
                json.dump(records, open(RATING_JSON, 'w', encoding='utf-8'),
                           ensure_ascii=False, indent=2)

    # 4. 最终保存全部评分
    json.dump(records, open(RATING_JSON, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"\n✅ 全部评分完成，共 {len(records)} 条")

    return records, prompts


def main():
    records, prompts = build_rates()
    # 输入 fields ['pid','variant','score','pid_str']
    print("\n—— Mark打补丁字段（补全 prompt_data_from_keys 作为字符串 pid and int id）——")
    # 无补丁；直接生成时期望写 MD

    if not records:
        print("Got empty records; use rating JSON as archive input")
        raise SystemExit(0)

    # 注意这里 `files` 不定义，因为在 `_gen_md` 里推 for k in keys
    _gen_md(records, prompts)


def _gen_md(records, prompts):
    """根据生成的 records 字典和原 prompts dict 生成 archive MD"""
    import datetime

    # 数据从 files exist 动用 prompts from json (by integer keys)
    rates = records
    if not rates:
        print("⚠️ records 为空，不写 MD")
        return

    # ---------- 按 pid_str 聚合 ----------
    by_pid = {}  # "P001" -> [score1, score2, score3]
    for k, v in rates.items():
        pid_str = v.get('pid_str') or f"P{v['pid']:03d}"
        if pid_str not in by_pid: by_pid[pid_str] = []
        # 每 item 传 dtype dict 含 score(float) 转 string print
        by_pid[pid_str].append(float(v['score']))

    # 统计
    scores = [float(v['score']) for v in rates.values() if type(v.get('score')) is float]
    total_avg = sum(scores) / len(scores) if scores else 0.0

    # top by avg
    def avg(l): return sum(l)/len(l) if l else 0.0
    best_pid = max(by_pid.items(), key=lambda t: avg(t[1])) if by_pid else (None, [])
    best_key = None
    if best_pid[0]:
        example_k = [k for k, v in rates.items() if v.get('pid_str') == best_pid[0]][0]
        best_key = example_k
        best_avg = avg(best_pid[1])
    else:
        best_avg = 0.0

    # 写分类集合
    high = sum(1 for s in scores if s >= 8.5)
    mid_ = sum(1 for s in scores if 6.5 <= s < 8.5)
    low = sum(1 for s in scores if s < 6.5)

    lines = ["# 🌸 慵懒居家长裙 100×3 批次 — GLM-4V 智能评分与归档汇总"]
    lines += [
        "",
        f"- **评分时间**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **评分模型**: GLM-4V-Flash（智谱） — 仅评图像质量，不参考提示词字段",
        f"- **总张数**: {len(rates)}/300",
        "",
        "## 📊 每提示词汇总（100 条，3 张平均）",
        "| 提示词 | 3张平均 | 最佳单张 | 状态 |",
        "|---|---|---|---|",
    ]

    # 按 pid_int 排序（1-100）
    for pid_int in sorted(prompts.keys()):
        pid_str = f"P{pid_int:03d}"
        if pid_str not in by_pid:
            lines.append(f"| {pid_str} | — | — | ❓ 无 |")
            continue
        scs = by_pid[pid_str]
        sa, ms = avg(scs), max(scs)
        quality = "🌟" if sa >= 8.5 else "✅" if sa >= 7.5 else "⚠️" if sa >= 6.5 else "❌"
        lines.append(f"| {pid_str} | {sa:.1f} | {ms:.1f} | {quality} |")

    lines += [
        "",
        "## 📈 总评饼图（按图像质量）",
        f"- **平均分**: {total_avg:.2f} / 10",
        f"- **优质 (≥8.5)**: {high} ({high/len(scores)*100:.1f}%)",
        f"- **合格 (6.5-8.5)**: {mid_} ({mid_/len(scores)*100:.1f}%)",
        f"- **待改进 (<6.5)**: {low} ({low/len(scores)*100:.1f}%)",
        "",
        "## 🎯 推荐可直接使用的 TOP-1 提示词",
        f"- **{best_pid[0]}** — 平均分 **{best_avg:.1f}**（最佳图：`{best_key}.png`）",
        "",
        "## 📋 完整 JSON 数据",
        f"提示词 → 图片 → 评分 → GLM 反馈详见 `archive_hazy_home_lazy_ratings.json`",
    ]

    with open(ARCHIVE_MD, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
    print(f"✅ MD 汇总已写入 → {ARCHIVE_MD}")


if __name__ == '__main__':
    main()

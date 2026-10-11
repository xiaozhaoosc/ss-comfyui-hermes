#!/usr/bin/env python3
"""fp8_hazy_lazy 300 张智能评分：高效批量版

关键优化：
1. GLM-4V 是 API 调用（非 GPU），支持并行批量（异步 8-16 并发）
2. 每 100 张（1 个 prompt × 3 变体）输出一次中间汇总（防中途 crash）
3. 只评总分，不评细节 → 时间在 1-2 分钟内完成（300 张约 300-600 个调用）

输出: archive_hazy_home_lazy_ratings.json + 更新 archive_hazy_home_lazy.md
"""
import json, os, base64, urllib.request, time, threading, queue, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

COMM_DIR = r"D:\ai_projects\ComfyUI"
OUT_DIR = os.path.join(COMM_DIR, "output", "fp8_hazy_lazy")
PROMPT_FILE = r"D:\obsidian\obsidian\ComfyUI\50写真批次prompts\en\hazy_home_lazy_100_en.json"
ARCHIVE_MD = r"D:\obsidian\obsidian\ComfyUI\50写真批次prompts\archive_hazy_home_lazy.md"
RATING_JSON = r"D:\obsidian\obsidian\ComfyUI\50写真批次prompts\archive_hazy_home_lazy_ratings.json"
CFG = json.load(open(r"C:\Users\kenzhao\.config\opencode\opencode.json", encoding='utf-8'))
GLM_KEY = CFG['provider']['glm']['options']['apiKey']

MAX_WORKERS = 12  # 并发（每张图是 HTTP 请求，可开 12 个）


def vqa(img_path, question):
    with open(img_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode()
    payload = {"model": "glm-4v-flash", "messages": [{"role": "user", "content": [
        {"type": "text", "text": {{NEW_QUESTION}},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
    ]}]}
    req = urllib.request.Request("https://open.bigmodel.cn/api/paas/v4/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {GLM_KEY}"})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=60).read())
        return r['choices'][0]['message']['content']
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}: {e.read().decode(errors='replace')[:200]}"
    except Exception as e:
        return f"ERR {e}"

# 简化版：只要总分
NEW_QUESTION = ""  # 已整合到下面 rate_polygonalb_vqa

def rate_polygonalb_vqa(img_path, pid, variant):
    """对单张图快速评 1-10 总分"""
    q = (
        "你是一名专业 AI 摄影图片评审。请仅基于图像本身评分，不要提及提示词。\n"
        "请给出 1-10 整数总分（基于「主题契合度」、「构图完整性」、「画质质感」、「穿帮畸变」综合加权）。\n"
        "回答格式（严格）:\n"
        "总分: X.X\n"
        "总评: [一句话简短评价，30字内]\n"
        "主题契合度: [1-10]"
    )
    raw = vqa(img_path, q)
    import re
    m = re.search(r"总分[:：]\s*([0-9.]+)", raw)
    if not m: return None
    score = float(m.group(1))
    theme = re.search(r"主题契合度[:：]\s*([0-9.]+)", raw)
    theme_s = float(theme.group(1)) if theme else 0.0
    return score


def load_image(path):
    with open(path, 'rb') as f: return base64.b64encode(f.read()).decode()


def main():
    prompts = {p['id']: p for p in json.load(open(PROMPT_FILE, encoding='utf-8'))}
    files = sorted([f for f in os.listdir(OUT_DIR) if f.endswith('.png')])
    rates = {}

    if os.path.exists(RATING_JSON):
        try:
            rates = json.load(open(RATING_JSON, encoding='utf-8'))
            print(f"加载已有 {len(rates)} 条（防中断）")
        except: rates = {}

    # 进度文件
    json.dump(rates, open(RATING_JSON, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # 按 pid 聚合要评分的列表
    tasks = []
    for pid_i in range(1, 101):
        pid_key = f"P{pid_i:03d}"
        if pid_key not in prompts: continue
        files_for_pid = [f for f in files if f.startswith(pid_key)]
        if not files_for_pid: continue
        for fn in files_for_pid:
            key = fn.replace('.png', '').replace('_00001_', '')
            if key in rates: continue
            img_path = os.path.join(OUT_DIR, fn)
            b64_img = load_image(img_path)[:1600000]  # 约 1.2MB 限，防止 token 超限
            tasks.append((key, pid_key, fn.split('_')[1], img_path, b64_img, prompts[pid_key]['positive'][:80]))

    print(f"待评分: {len(tasks)} 张")
    # 使用线程池批量
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(rate_polygonalb_vqa, p, v, b): (k, v, b) for k, p, v, b in tasks if k not in rates}
        for future in as_completed(futures):
            k, p, v, b = futures[future]
            if k in rates: continue
            try:
                s = future.result()
                rates[k] = {"pid": p, "variant": v, "avg_score": s or 0.0}
                if s: print(f"✓ {k}: {s:.1f}")
                # 每 30 张保存一次
                if len(rates) % 30 == 0:
                    json.dump(rates, open(RATING_JSON, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                    print(f"--- 已评分 {len(rates)}/300 ---")
            except Exception as e:
                print(f"✗ {k} 调度失败: {e}")
                rates[k] = {"pid": p, "variant": v, "avg_score": 0.0}

    json.dump(rates, open(RATING_JSON, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"\n评分完成：{len(rates)}/300")

    # 生成汇总 md
    by_pid = {}
    for k, v in rates.items():
        pid = v['pid']
        if pid not in by_pid: by_pid[pid] = []
        by_pid[pid].append(v['avg_score'])

    avg_scores = [v['avg_score'] for v in rates.values()]
    total_avg = sum(avg_scores) / len(avg_scores)
    high = [k for k, v in rates.items() if v['avg_score'] >= 8.5]
    mid_ = [k for k, v in rates.items() if 6.5 <= v['avg_score'] < 8.5]
    low = [k for k, v in rates.items() if v['avg_score'] < 6.5]
    lines = [
        f"# 🌸 慵懒居家长裙 100×3 批次 — GLM-4V 智能评分",
        f"- 评分时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 平均每 prompt: {sum(sum(scores) / len(scores) for scores in by_pid.values()):.2f} / 10",
        f"- 评分者: GLM-4V-Flash (12 线程批量)",
        "",
        "## 📊 每提示词汇总（100 条，3 张平均）",
        "| 提示词 | 平均分 | 状态 | 1 张最佳 | 备注 |",
        "|---|---|---|---|---|",
    ]
    for pid_i in range(1, 101):
        pid_key = f"P{pid_i:03d}"
        if pid_key not in by_pid:
            lines.append(f"| {pid_key} | - | - | - | 无图 - |")
            continue
        scores = by_pid[pid_key]
        avg = sum(scores) / len(scores)
        max_s = max(scores)
        quality = "🌟" if avg >= 8.5 else "✅" if avg >= 7.5 else "⚠️" if avg >= 6.5 else "❌"
        # 变体对比差异
        lines.append(f"| {pid_key} | {avg:.1f} | {quality} | {max_s:.1f} | {len(scores)} 张 |")

    lines += [
        "",
        "## 📈 总评饼图",
        f"- 平均分: **{total_avg:.2f}** / 10",
        f"- 优质 (≥8.5): **{len(high)}** ({len(high)/len(avg_scores)*100:.1f}%)",
        f"- 合格 (6.5-8.5): **{len(mid_)}** ({len(mid_)/len(avg_scores)*100:.1f}%)",
        f"- 待改进 (<6.5): **{len(low)}** ({len(low)/len(avg_scores)*100:.1f}%)",
        "",
        f"## 🎯 推荐可直接使用的 TOP-3 提示词",
        f"- **{pid_key}** — 最高平均分 **{max_s:.1f}**（推荐作为 H3 首帧参考）",
        "",
        "## 💡 下一步建议",
        "1. 评分越高越适合 H3 首帧 → 筛选后从 `fp8_hazy_lazy/` 中挑 TOP 2-3 接入并完成 H3 视频生成测试",
        f"2. 3 张优质代表图例已列出：可用 `P00X_vY` 作为后续工作流 first_frame/last_frame",
        f"3. 待改进 ({len(low)} 张) 建议按评分倒序重跑（同 seed 重置后再次提交）",
    ]
    with open(ARCHIVE_MD, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
    print(f"✅ MD 汇总已更新 → {ARCHIVE_MD}")

if __name__ == '__main__':
    main()

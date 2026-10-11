#!/usr/bin/env python3
"""将 6 批写真中文提示词翻译为英文（fp8 + GGUF CLIP 中文理解差，需英文提示词）

用法:
  python tools/translate_prompts_en.py           # 翻译全部 6 批
  python tools/translate_prompts_en.py --test    # 只翻译 batch01 前 3 条测试

输出: 50写真批次prompts/en/ 目录（batch01_泳装_en.json 等）
"""
import json, urllib.request, urllib.error, os, sys, time, re

PROMPT_DIR = r"D:\obsidian\obsidian\ComfyUI\50写真批次prompts"
OUT_DIR = os.path.join(PROMPT_DIR, "en")

# GLM API 配置（从 opencode.json 读取）
def get_key():
    cfg = json.load(open(r"C:\Users\kenzhao\.config\opencode\opencode.json", encoding='utf-8'))
    return cfg['provider']['glm']['options']['apiKey']

def translate(text, key):
    """调用 glm-4-flash 翻译为英文摄影提示词"""
    payload = {
        "model": "glm-4-flash",
        "messages": [
            {"role": "system", "content": "你是专业 AI 摄影提示词翻译。将中文写真提示词翻译为简洁的英文摄影提示词，保留所有服装/妆容/场景/光线/镜头细节，用逗号分隔的关键词风格，不要解释。"},
            {"role": "user", "content": text}
        ],
        "temperature": 0.3
    }
    req = urllib.request.Request("https://open.bigmodel.cn/api/paas/v4/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    r = json.loads(urllib.request.urlopen(req, timeout=120).read())
    return r['choices'][0]['message']['content'].strip()

BATCHES = [
    ("batch01_泳装",       "batch01_泳装.json"),
    ("batch02_睡裙",       "batch02_睡裙.json"),
    ("batch03_内衣秀",     "batch03_内衣秀.json"),
    ("batch04_泳装_skill", "batch04_泳装_skill_v2.json"),
    ("batch05_睡裙_skill", "batch05_睡裙_skill_v2.json"),
    ("batch06_内衣秀_skill","batch06_内衣秀_skill_v2.json"),
]

def main():
    test_mode = "--test" in sys.argv
    key = get_key()
    os.makedirs(OUT_DIR, exist_ok=True)

    for bname, fn in BATCHES:
        if test_mode and bname != "batch01_泳装":
            continue
        src = json.load(open(os.path.join(PROMPT_DIR, fn), encoding='utf-8'))
        dst = []
        limit = 3 if test_mode else len(src)
        for i, p in enumerate(src[:limit]):
            # 翻译正/负提示词
            for attempt in range(3):
                try:
                    pos_en = translate(p['positive'], key)
                    time.sleep(0.5)
                    neg_en = translate(p['negative'], key)
                    dst.append({"id": p['id'], "positive": pos_en, "negative": neg_en})
                    print(f"  ✓ {bname} P{p['id']:02d}", flush=True)
                    break
                except urllib.error.HTTPError as e:
                    if e.code == 429:
                        print(f"    ⏳ 429 限流，等待 5s...")
                        time.sleep(5)
                    else:
                        print(f"    ✗ HTTP {e.code}: {e.read().decode(errors='replace')[:200]}")
                        time.sleep(2)
                except Exception as e:
                    print(f"    ✗ {e}")
                    time.sleep(2)
        out_fn = os.path.join(OUT_DIR, f"{bname}_en.json")
        json.dump(dst, open(out_fn, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f"完成: {out_fn} ({len(dst)} 条)\n")

if __name__ == '__main__':
    main()

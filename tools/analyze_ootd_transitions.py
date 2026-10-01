#!/usr/bin/env python3
"""用 GLM-4V-Flash 分析 OOTD 换装转场质量（免费，串行避并发限制）"""
import base64, json, os, sys, time, urllib.request, urllib.error
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

BASE_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
KEY = os.environ.get("GLM_API_KEY") or "f2649c2b4bef47b099bf63a63ce135e4.kpn7Es4gyg3dawQk"
MODEL = "glm-4v-flash"

PROMPT_TEMPLATE = """请用中文回答以下4个问题，每个问题答案用单行输出，一行一项（共4行）：
1. 该帧中人物的服装/颜色
2. 动作姿态
3. 是否为换装转场中的「中间过渡帧」（是/否）
4. 如果是中间帧，它的序号/时间戳（估计即可）

请严格按一行一答的格式输出，不要 markdown 表格、不要换行、不要 | 符号。"""

FRAMES_DIR = Path("output/ootd_v1/frames")
OUT_FILE = Path("output/ootd_v1/transitions_analysis.json")

def glm_vision(img_path, prompt):
    b64 = base64.b64encode(open(img_path, "rb").read()).decode()
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
        ]}]
    }
    # 重试 5 次：网络错误/SSL 错误/429 都等几秒重来
    for attempt in range(5):
        try:
            req = urllib.request.Request(
                BASE_URL,
                data=json.dumps(payload).encode(),
                headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
            )
            d = json.loads(urllib.request.urlopen(req, timeout=120).read())
            return d["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(5); continue
            return f"[HTTP {e.code}]"
        except Exception as e:
            # SSL EOF / 连接问题 → 等 10s 重试
            print(f"    ⚠️ 第{attempt+1}次请求失败: {type(e).__name__}: {str(e)[:80]}，重试...", flush=True)
            time.sleep(8)
    return "[请求失败]"

def extract_frames(vname):
    # 帧文件名格式: {vname}_00001_f{0,1,2,3}.png
    frames = sorted(FRAMES_DIR.glob(f"{vname}_*_f*.png"),
                    key=lambda p: int(p.stem.rsplit("_f", 1)[1]))
    return frames

def main():
    videos = [
        "v01_御姐显瘦", "v02_甜韩显嫩", "v03_御姐舞蹈", "v04_夏日御姐",
        "v05_纯欲显瘦", "v06_纯欲御姐舞蹈", "v07_梨型显瘦", "v08_甜韩显嫩"
    ]
    
    results = {}
    print(f"共 {len(videos)} 个视频分析\n")
    
    for i, vname in enumerate(videos, 1):
        frames = extract_frames(vname)
        if not frames:
            print(f"⚠️ [{i}/8] {vname}: 无帧")
            continue
        
        record = {"frames": {}, "duration_s": 8.0}
        
        for j, frame_path in enumerate(frames):
            frames_desc = ["首(0.1s)", "中1(t≈33%)", "中2(t≈66%)", "尾(t≈92.7%)"]
            t_label = frames_desc[j] if j < len(frames_desc) else f"帧{j}"
            
            prompt = f"此帧是换装视频的【{t_label}】（总时长8秒，输出：{vname}）。"+ PROMPT_TEMPLATE
            
            ans = glm_vision(str(frame_path), prompt)
            
            # 解析答案（用 | 分隔）
            parts = [p.strip() for p in ans.split("|")]
            record["frames"][t_label] = {
                "服装": parts[0] if len(parts) > 0 else "未识别",
                "动作": parts[1] if len(parts) > 1 else "未识别",
                "过渡帧": parts[2] if len(parts) > 2 else "未识别",
                "过渡时间": parts[3] if len(parts) > 3 else "未识别",
                "原始回答": ans
            }
            time.sleep(1)  # 串行避免并发超限
        
        results[vname] = record
        # 保存一次
        with open(OUT_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"[{i}/8] {vname}: 已分析：")
        for f_label, d in record["frames"].items():
            print(f"  {f_label}: {d['服装'][:40]}")
    
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n\n分析结果已存: {OUT_FILE}")

if __name__ == "__main__":
    main()

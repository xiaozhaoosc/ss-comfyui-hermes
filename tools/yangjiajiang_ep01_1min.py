#!/usr/bin/env python3
"""北宋杨家将 · 第一集《金沙滩前夕》前 1 分钟样片全链路制作管线

功能：
1. 制作专属性 60 秒原声设计音频轨（干净无杂音，依据《杨家将_逐镜头脚本.xlsx》分镜音效与环境音精确对位）：
   - 0:00-0:08 (镜1): 由远及近的风沙呼啸声
   - 0:08-0:12 (镜2): 2秒处木头撞击石头的沉闷短促重击声与回荡
   - 0:12-0:16 (镜3): 默片级悬念静音（零噪音纯静）
   - 0:16-0:24 (镜4-5): 低频暗涌风声与宣纸朱砂渗透微声
   - 0:24-0:30 (镜6): 旷野风声混入远方隐约马蹄声
   - 0:30-0:36 (镜7): 苍茫浑厚的低音钟鸣伴随片名出
   - 0:36-0:46 (镜8-9): 塞外清晨凛冽寒风呼啸
   - 0:46-0:55 (镜10-11): 军旗在狂风中激烈猎猎撕扯抽打声
   - 0:55-1:00 (镜12): 塞外寒风与铁甲轻微摩挲声
2. 逐镜生成/调度对应视觉素材（画幅 16:9，960x544）：
   - 镜1-3: 全黑画面（16秒）
   - 镜4-6, 8-12: H3 4-Step Turbo I2V 极速生成对应动态
   - 镜7: 题字木刻版画片名卡平稳运镜
3. 自动将 12 镜合成为 60.0 秒完整样片并混流干净音频轨，输出至 output/2026-10-04/yangjiajiang_ep01/
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error
import numpy as np
from scipy.io import wavfile
from scipy import signal

ROOT = r"D:\ai_projects\ComfyUI"
INPUT_ROOT = os.path.join(ROOT, "input")
DATE_STR = "2026-10-04"
OUTPUT_DIR = os.path.join(ROOT, "output", DATE_STR, "yangjiajiang_ep01")
WORKFLOW_PATH = os.path.join(ROOT, "workflows", "v5", "h3_fast_i2v_9x16_api.json")
FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
if not os.path.exists(FFMPEG):
    FFMPEG = shutil.which("ffmpeg") or "ffmpeg"

BASE_URL = "http://127.0.0.1:8188"

# 12 镜头规格
EP01_SHOTS = [
    {
        "id": 1,
        "name": "shot01_black",
        "title": "风沙开篇",
        "type": "black",
        "sec": 8.0,
    },
    {
        "id": 2,
        "name": "shot02_impact",
        "title": "异响惊破",
        "type": "black",
        "sec": 4.0,
    },
    {
        "id": 3,
        "name": "shot03_silence",
        "title": "死寂悬念",
        "type": "black",
        "sec": 4.0,
    },
    {
        "id": 4,
        "name": "shot04_cinnabar",
        "title": "朱砂下渗",
        "type": "i2v",
        "input_image": "yang_ep01_shot04.jpg",
        "sec": 4.0,
        "length": 124,
        "prompt": "Camera static, cinnabar red mineral pigment slowly bleeds and spreads downward across black raw Xuan paper, organic capillary bleeding, slow motion, vintage Shanghai Animation Film Studio ink wash manner.",
    },
    {
        "id": 5,
        "name": "shot05_crimson_sun",
        "title": "残阳初现",
        "type": "i2v",
        "input_image": "yang_ep01_shot05.jpg",
        "sec": 4.0,
        "length": 124,
        "prompt": "Camera static, circular red ink pigment gently expands outward to form a hazy crimson sun disk, subtle bleeding edges, calm and solemn, traditional hand-painted Chinese 2D animation style.",
    },
    {
        "id": 6,
        "name": "shot06_horizon",
        "title": "焦墨地平线",
        "type": "i2v",
        "input_image": "yang_ep01_shot06.jpg",
        "sec": 6.0,
        "length": 141,
        "prompt": "Very slow camera pan right, scorched black ink horizon stretches endlessly beneath the setting crimson sun, lonely desolate Song dynasty frontier wasteland, traditional Chinese ink wash landscape.",
    },
    {
        "id": 7,
        "name": "shot07_titlecard",
        "title": "片名题字",
        "type": "title",
        "input_image": "yang_ep01_shot07.jpg",
        "sec": 6.0,
    },
    {
        "id": 8,
        "name": "shot08_frosty_dawn",
        "title": "薄霜晨景",
        "type": "i2v",
        "input_image": "yang_ep01_shot08.jpg",
        "sec": 4.0,
        "length": 124,
        "prompt": "Very slow camera forward drift, misty frosty dawn on Northern Song frontier, vast empty grey snowfield, cold and silent atmosphere, traditional mineral pigment 2D animation style.",
    },
    {
        "id": 9,
        "name": "shot09_outpost_tower",
        "title": "孤峙哨堡",
        "type": "i2v",
        "input_image": "yang_ep01_shot09.jpg",
        "sec": 6.0,
        "length": 141,
        "prompt": "Camera very slowly zooms in toward the lone stone military watchtower fortress on the desolate snow plain, cold bleak morning, traditional Chinese ink wash brushwork style.",
    },
    {
        "id": 10,
        "name": "shot10_tower_flag",
        "title": "堡顶残旗",
        "type": "i2v",
        "input_image": "yang_ep01_shot10.jpg",
        "sec": 4.0,
        "length": 124,
        "prompt": "Camera pushes in steadily toward the watchtower, black army banner flapping violently in the bitter winter wind, stone fortress in the freezing mountains.",
    },
    {
        "id": 11,
        "name": "shot11_banner_closeup",
        "title": "宋字军旗特写",
        "type": "i2v",
        "input_image": "yang_ep01_shot11.jpg",
        "sec": 5.0,
        "length": 124,
        "prompt": "Close-up of ragged black Song army flag flapping violently in the winter gale, fabric ripples and strains, dust and snow drifting past, traditional 2D animation aesthetic.",
    },
    {
        "id": 12,
        "name": "shot12_sentinel",
        "title": "守望哨兵",
        "type": "i2v",
        "input_image": "yang_ep01_shot12.jpg",
        "sec": 5.0,
        "length": 124,
        "prompt": "Young Song soldier on watch, subtle breathing and blinking in the freezing wind, chapped red cheeks, looking into the distant snowy horizon, traditional hand-painted anime style.",
    },
]


def generate_clean_audio(output_wav_path, sample_rate=44100):
    """合成 60 秒广播级电影原声与音效设计轨（零 DiT 杂音）"""
    total_seconds = 60.0
    num_samples = int(total_seconds * sample_rate)
    audio = np.zeros(num_samples, dtype=np.float32)

    # 1. 0:00 - 0:08 (镜1): 风沙由远及近渐强
    t1 = np.linspace(0, 8.0, int(8.0 * sample_rate), endpoint=False)
    raw_noise1 = np.random.normal(0, 0.15, len(t1))
    sos1 = signal.butter(4, [80, 450], btype='bandpass', fs=sample_rate, output='sos')
    wind1 = signal.sosfilt(sos1, raw_noise1)
    # 渐强包络 0.1 -> 0.8
    env1 = np.linspace(0.08, 0.8, len(t1)) ** 1.5
    idx1_end = int(8.0 * sample_rate)
    audio[:idx1_end] += (wind1 * env1).astype(np.float32)

    # 2. 0:08 - 0:12 (镜2): 风声暂歇，并在 2.0s 处（对应 10.0s）发生重击
    idx2_start = int(8.0 * sample_rate)
    idx2_end = int(12.0 * sample_rate)
    t2 = np.linspace(0, 4.0, idx2_end - idx2_start, endpoint=False)
    # 风声迅速减弱
    wind2_env = np.maximum(0.0, 0.8 - t2 * 0.4)
    raw_noise2 = np.random.normal(0, 0.15, len(t2))
    wind2 = signal.sosfilt(sos1, raw_noise2) * wind2_env
    # 10.0s 处的重击 (t = 2.0s)
    impact_t = t2 - 2.0
    impact_mask = impact_t >= 0
    decay = np.exp(-impact_t[impact_mask] * 12.0)
    # 模拟木头撞击石头的低频共鸣与脆裂瞬态
    thud_synth = (np.sin(2 * np.pi * 55 * impact_t[impact_mask]) * 0.7 +
                  np.sin(2 * np.pi * 120 * impact_t[impact_mask]) * 0.4 +
                  np.sin(2 * np.pi * 260 * impact_t[impact_mask]) * 0.2) * decay
    # 撞击瞬态冲击波
    click_noise = np.random.normal(0, 0.6, len(decay)) * np.exp(-impact_t[impact_mask] * 60.0)
    impact_total = (thud_synth + click_noise) * 0.95
    impact_full = np.zeros(len(t2), dtype=np.float32)
    impact_full[impact_mask] = impact_total
    audio[idx2_start:idx2_end] += (wind2 + impact_full).astype(np.float32)

    # 3. 0:12 - 0:16 (镜3): 纯静音，悬念（已保持 0）

    # 4. 0:16 - 0:24 (镜4-5): 极低频暗涌氛围与纸上朱砂晕开
    idx4_start = int(16.0 * sample_rate)
    idx4_end = int(24.0 * sample_rate)
    t4 = np.linspace(0, 8.0, idx4_end - idx4_start, endpoint=False)
    drone_sos = signal.butter(4, [35, 120], btype='bandpass', fs=sample_rate, output='sos')
    drone_noise = signal.sosfilt(drone_sos, np.random.normal(0, 0.2, len(t4)))
    drone_sub = np.sin(2 * np.pi * 48.0 * t4) * 0.12
    drone_env = np.minimum(1.0, t4 / 3.0)
    audio[idx4_start:idx4_end] += ((drone_noise + drone_sub) * drone_env).astype(np.float32)

    # 5. 0:24 - 0:30 (镜6): 旷野风声与远方马蹄
    idx6_start = int(24.0 * sample_rate)
    idx6_end = int(30.0 * sample_rate)
    t6 = np.linspace(0, 6.0, idx6_end - idx6_start, endpoint=False)
    wind6 = signal.sosfilt(sos1, np.random.normal(0, 0.15, len(t6))) * 0.35
    # 模拟远方微弱马蹄 (每秒 3 下节奏)
    hoof_pulses = np.zeros(len(t6), dtype=np.float32)
    for h_t in np.arange(0.5, 5.8, 0.35):
        h_idx = int(h_t * sample_rate)
        if h_idx < len(t6) - 500:
            hoof_pulses[h_idx:h_idx+400] += np.hanning(400) * 0.15
    audio[idx6_start:idx6_end] += (wind6 + hoof_pulses).astype(np.float32)

    # 6. 0:30 - 0:36 (镜7): 题字片名出，深沉庄严的低音钟鸣
    idx7_start = int(30.0 * sample_rate)
    idx7_end = int(36.0 * sample_rate)
    t7 = np.linspace(0, 6.0, idx7_end - idx7_start, endpoint=False)
    gong_decay = np.exp(-t7 * 0.8)
    gong_synth = (np.sin(2 * np.pi * 65 * t7) * 0.5 +
                  np.sin(2 * np.pi * 130 * t7) * 0.3 +
                  np.sin(2 * np.pi * 215 * t7) * 0.15) * gong_decay * 0.6
    audio[idx7_start:idx7_end] += gong_synth.astype(np.float32)

    # 7. 0:36 - 0:46 (镜8-9): 塞外清晨凛冽寒风呼啸
    idx8_start = int(36.0 * sample_rate)
    idx8_end = int(46.0 * sample_rate)
    t8 = np.linspace(0, 10.0, idx8_end - idx8_start, endpoint=False)
    cold_sos = signal.butter(4, [120, 650], btype='bandpass', fs=sample_rate, output='sos')
    cold_wind = signal.sosfilt(cold_sos, np.random.normal(0, 0.25, len(t8))) * 0.45
    audio[idx8_start:idx8_end] += cold_wind.astype(np.float32)

    # 8. 0:46 - 0:55 (镜10-11): 军旗在风中剧烈猎猎抽打作响
    idx10_start = int(46.0 * sample_rate)
    idx10_end = int(55.0 * sample_rate)
    t10 = np.linspace(0, 9.0, idx10_end - idx10_start, endpoint=False)
    flag_wind = signal.sosfilt(cold_sos, np.random.normal(0, 0.25, len(t10))) * 0.4
    # 抽打与撕扯音效
    flag_flaps = np.zeros(len(t10), dtype=np.float32)
    rng = np.random.default_rng(20261004)
    flap_times = np.cumsum(rng.uniform(0.18, 0.38, 30))
    flap_times = flap_times[flap_times < 9.0]
    for ft in flap_times:
        f_idx = int(ft * sample_rate)
        f_len = rng.integers(1200, 2600)
        if f_idx + f_len < len(t10):
            burst = rng.normal(0, 0.35, f_len) * np.hanning(f_len)
            flag_flaps[f_idx:f_idx+f_len] += burst.astype(np.float32)
    audio[idx10_start:idx10_end] += (flag_wind + flag_flaps * 0.6).astype(np.float32)

    # 9. 0:55 - 1:00 (镜12): 守望哨兵，寒风渐远
    idx12_start = int(55.0 * sample_rate)
    t12 = np.linspace(0, 5.0, num_samples - idx12_start, endpoint=False)
    wind12 = signal.sosfilt(cold_sos, np.random.normal(0, 0.18, len(t12))) * np.linspace(0.4, 0.2, len(t12))
    audio[idx12_start:] += wind12.astype(np.float32)

    # 音量峰值标准化 (-1.5 dB)
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = (audio / max_val) * 0.84

    # 立体声微展宽
    stereo_audio = np.stack([audio, audio * 0.98 + np.roll(audio, 120) * 0.05], axis=-1)
    stereo_int16 = (stereo_audio * 32767).astype(np.int16)

    os.makedirs(os.path.dirname(output_wav_path), exist_ok=True)
    wavfile.write(output_wav_path, sample_rate, stereo_int16)
    print(f"[音频设计] 60秒无杂音纯净电影原声轨已生成: {output_wav_path}")
    return output_wav_path


def post_json(path, payload, timeout=60):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(path, timeout=30):
    with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def inject_workflow(wf_template, shot, width=960, height=544, seed=20261004):
    prefix = f"{DATE_STR}/yangjiajiang_ep01/{shot['name']}"
    values = {
        "first_frame": shot["input_image"],
        "prompt": shot["prompt"],
        "width": width,
        "height": height,
        "length": shot["length"],
        "seed": seed + shot["id"] * 13,
        "filename_prefix": prefix,
    }

    def walk(obj):
        if isinstance(obj, str):
            if obj.startswith("[inject:") and obj.endswith("]"):
                k = obj[len("[inject:"):-1]
                return values[k]
            return obj
        if isinstance(obj, list):
            return [walk(x) for x in obj]
        if isinstance(obj, dict):
            return {k: walk(v) for k, v in obj.items()}
        return obj

    return walk(wf_template)


def wait_prompt_done(prompt_id, timeout=900, poll=10):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            hist = get_json(f"/history/{prompt_id}")
        except Exception:
            time.sleep(poll)
            continue
        if prompt_id in hist:
            item = hist[prompt_id]
            st = item.get("status", {})
            if st.get("status_str") == "error":
                print(f"  [执行失败] prompt_id={prompt_id}: {st}")
                return None
            outputs = item.get("outputs", {})
            for nid, out in outputs.items():
                for k, v in out.items():
                    if isinstance(v, list):
                        for file_info in v:
                            if isinstance(file_info, dict) and "filename" in file_info:
                                sub = file_info.get("subfolder", "")
                                fn = file_info["filename"]
                                full_p = os.path.join(ROOT, "output", sub, fn)
                                if os.path.exists(full_p) and full_p.endswith((".mp4", ".mov", ".mkv")):
                                    return full_p
            if item.get("status", {}).get("completed"):
                return True
        time.sleep(poll)
    print(f"  [等待超时] prompt_id={prompt_id}")
    return None


def generate_black_clip(output_path, duration):
    """生成指定秒数的纯黑无缝视频片段"""
    cmd = [
        FFMPEG, "-y",
        "-f", "lavfi",
        "-i", f"color=c=black:s=960x544:r=24",
        "-t", str(duration),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        output_path
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path


def generate_title_card_clip(input_img, output_path, duration=6.0):
    """为片名题字生成微幅运镜视频，避免 DiT 破坏书法刻版质感"""
    input_full = os.path.join(INPUT_ROOT, input_img)
    cmd = [
        FFMPEG, "-y",
        "-loop", "1",
        "-i", input_full,
        "-vf", "scale=960:544,format=yuv420p",
        "-t", str(duration),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        output_path
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path


def main():
    parser = argparse.ArgumentParser(description="第一集前1分钟样片生成与原声混流")
    parser.add_argument("--skip-render", action="store_true", help="跳过渲染，仅重新混流拼接")
    parser.add_argument("--shot", type=int, default=0, help="单跑某镜")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    audio_wav = os.path.join(OUTPUT_DIR, "ep01_1min_audio_track.wav")
    generate_clean_audio(audio_wav)

    with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
        wf_template = json.load(f)

    # 逐镜处理
    rendered_clips = {}
    for s in EP01_SHOTS:
        if args.shot > 0 and s["id"] != args.shot:
            continue
        clip_name = f"{s['name']}.mp4"
        clip_path = os.path.join(OUTPUT_DIR, clip_name)

        if os.path.exists(clip_path) and not args.shot:
            print(f"[跳过已有] 镜 {s['id']:02d} ({s['title']}): {clip_path}")
            rendered_clips[s["id"]] = clip_path
            continue

        print(f"\n>>> 正在准备【镜 {s['id']:02d}：{s['title']}】 (时长 {s['sec']}s, 类型: {s['type']})")
        if s["type"] == "black":
            generate_black_clip(clip_path, s["sec"])
            print(f"    [完成] 黑屏片段生成: {clip_path}")
            rendered_clips[s["id"]] = clip_path
        elif s["type"] == "title":
            generate_title_card_clip(s["input_image"], clip_path, s["sec"])
            print(f"    [完成] 片名题字片段生成: {clip_path}")
            rendered_clips[s["id"]] = clip_path
        elif s["type"] == "i2v":
            wf = inject_workflow(wf_template, s)
            resp = post_json("/prompt", {"prompt": wf})
            pid = resp.get("prompt_id")
            print(f"    已提交 ComfyUI I2V, prompt_id: {pid}")
            video_done = wait_prompt_done(pid)
            if video_done and os.path.exists(video_done):
                # 规范重命名为固定镜头文件名
                shutil.copy(video_done, clip_path)
                print(f"    [完成] I2V 渲染落盘: {clip_path}")
                rendered_clips[s["id"]] = clip_path
            else:
                print(f"    [失败] 镜头 {s['id']} 生成失败")
                return 1

    if args.shot > 0:
        print(f"单镜 {args.shot} 处理完成。")
        return 0

    # 拼接并混流无杂音音频
    print("\n=== 开始拼接全 12 镜视频并混流 60 秒原声音效轨 ===")
    concat_txt = os.path.join(OUTPUT_DIR, "concat_12shots.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for s in EP01_SHOTS:
            cpath = os.path.join(OUTPUT_DIR, f"{s['name']}.mp4").replace("\\", "/")
            f.write(f"file '{cpath}'\n")

    temp_video_merged = os.path.join(OUTPUT_DIR, "temp_video_merged.mp4")
    concat_cmd = [
        FFMPEG, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_txt,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        temp_video_merged
    ]
    subprocess.run(concat_cmd, capture_output=True, check=True)

    final_merged = os.path.join(OUTPUT_DIR, "yang_ep01_1min_clean.mp4")
    mux_cmd = [
        FFMPEG, "-y",
        "-i", temp_video_merged,
        "-i", audio_wav,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        final_merged
    ]
    subprocess.run(mux_cmd, capture_output=True, check=True)

    if os.path.exists(final_merged):
        print(f"\n[成片交付] 第一集前 1 分钟纯净原声样片已生成: {final_merged}")
        # 输出成片详细流信息
        dur_cmd = [FFMPEG, "-i", final_merged]
        probe = subprocess.run(dur_cmd, capture_output=True, text=True)
        for line in probe.stderr.splitlines():
            if "Duration:" in line or "Video:" in line or "Audio:" in line:
                print(f"  {line.strip()}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())

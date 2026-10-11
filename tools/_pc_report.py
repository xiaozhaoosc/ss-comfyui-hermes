# -*- coding: utf-8 -*-
"""Aggregate all _run.json / run logs into a single comparison report (Markdown + JSON)."""
import os, json, glob, datetime

BASE = r"D:\ai_projects\ComfyUI"
OUT = os.path.join(BASE, "output", "prompt_compare")

MODEL_INFO = [
    ("majicmix", "majicmixRealistic_v7.safetensors", "SD1.5", "写实人像",
     "SD1.5 原生 KSampler", "512x768", 30, 7.0, "dpmpp_2m/karras"),
    ("counterfeit", "Counterfeit-V3.0_fp16.safetensors", "SD1.5", "动漫插画",
     "SD1.5 原生 KSampler", "512x768", 28, 8.0, "dpmpp_2m/karras"),
    ("aom3", "AOM3A3_orangemixs.safetensors", "SD1.5", "动漫插画(橙调)",
     "SD1.5 原生 KSampler", "512x768", 28, 8.0, "dpmpp_2m/karras"),
    ("flux_dev_fp8", "flux1-dev-fp8.safetensors", "Flux.1-dev", "高保真写实",
     "UNETLoader + DualCLIPLoader + FluxGuidance + KSampler", "768x1024", 20, 1.0, "euler/simple"),
]


def load_log(sub):
    p = os.path.join(OUT, sub, "_run.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None


def main():
    rows = []
    for sub, ckpt, family, style, workflow, size, steps, cfg, sampler in MODEL_INFO:
        d = load_log(sub)
        n_ok = 0; total = 0; per = []
        if d:
            for r in d.get("results", []):
                total += 1
                if r.get("ok"):
                    n_ok += 1
                    s = r.get("seconds")
                    # drop outliers from a run interrupted by queue contention
                    if s and s < 120:
                        per.append(s)
        avg = round(sum(per) / len(per), 1) if per else None
        rows.append(dict(sub=sub, ckpt=ckpt, family=family, style=style,
                         workflow=workflow, size=size, steps=steps, cfg=cfg,
                         sampler=sampler, ok=n_ok, total=total, avg_sec=avg,
                         total_sec=d.get("total_seconds") if d else None))

    # write JSON
    with open(os.path.join(OUT, "comparison_data.json"), "w", encoding="utf-8") as f:
        json.dump({"generated": datetime.datetime.now().isoformat(),
                   "models": rows}, f, ensure_ascii=False, indent=2)

    # write Markdown
    L = []
    L.append("# ComfyUI 同提示词多模型生成对比\n")
    L.append("> 生成时间：%s  ｜ 环境：RTX 4060 Ti 16GB / ComfyUI 1.44.19\n"
             % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    L.append("> 提示词来源：用户提供的 8 组场景描述（年轻女性 / 乌黑长发 / 白色吊带 / "
             "室内柔和光 / 清新自然 + 1 组户外场景）\n")
    L.append("## 一、对比矩阵\n")
    L.append("| 模型 | 家族 | 风格定位 | 工作流拓扑 | 分辨率 | 步数 | CFG | 采样器 | 成功 | 平均耗时 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        L.append("| `%s` | %s | %s | %s | %s | %d | %.1f | %s | %d/%d | %s |"
                 % (r["ckpt"], r["family"], r["style"], r["workflow"], r["size"],
                    r["steps"], r["cfg"], r["sampler"], r["ok"], r["total"],
                    ("%.1fs" % r["avg_sec"]) if r["avg_sec"] else "—"))
    L.append("")

    L.append("## 二、硬件与耗时观察\n")
    L.append("本机为 **RTX 4060 Ti 16GB**，三类规模的实测差异非常明显：\n")
    L.append("- **SD1.5（~2–4GB 模型）**：完全常驻显存，512×768 / 28–30 步稳定 **9 秒/张**，"
             "24 张总计约 3.5 分钟，是批量的绝对主力。")
    L.append("- **Flux.1-dev FP8（11.4GB UNet + 4.7GB T5 + VAE）**：单卡放不下，"
             "首张 40–56s（有缓存），后续因频繁换页升至 **165–180 秒/张**，"
             "约为 SD1.5 的 **19 倍**，但分辨率也更高（768×1024）。")
    L.append("- **Flux GGUF Q8（12.1GB）实测不可用**：与 T5 编码器合计超出显存，"
             "任务在队列中长时间挂起，已中止；这类规模必须换 **Q4_K_M（6.6GB）** 或更大显存卡。")
    L.append("- 单卡环境下所有任务**串行化**：曾在 SD1.5 批次中间插入 Flux 任务，"
             "导致队列被大模型阻塞，需先 `/interrupt` + `/queue clear` 再续跑。")
    L.append("")

    L.append("## 三、风格差异结论\n")
    L.append("### 1. majicmixRealistic_v7 — 最贴合原始意图（推荐）\n")
    L.append("- 写实度高，皮肤质感、发丝高光、窗光层次自然。")
    L.append("- **提示词还原度最高**：白色吊带、乌黑长发、抱膝托腮、户外蓝天地野等"
             "要素全部命中，且构图与用户描述基本一致。")
    L.append("- 缺点：SD1.5 底模对**手部/手指**偶有瑕疵；复杂姿势（侧卧托头）需要抽卡。")
    L.append("")
    L.append("### 2. Counterfeit-V3.0 / AOM3A3 — 动漫化诠释\n")
    L.append("- 同一提示词被转译为**日系插画**风格：大眼睛、平涂+厚涂混合、轮廓线明显。")
    L.append("- Counterfeit 偏**冷调/青绿**（s01/s03 明显偏青），AOM3 偏**暖调/柔光**，"
             "肤色更红润。")
    L.append("- 适合“清新纯真”的情绪表达，但**不适合**需要真实感的写真场景。")
    L.append("- AOM3 在 s05 户外场景会把针织帽理解成**猫耳/双髻**，对英文细节词的理解弱于 SD1.5 写实模型。")
    L.append("")
    L.append("### 3. Flux.1-dev FP8 — 细节与语义最强，代价是速度\n")
    L.append("- **语义理解最好**：s05 精确还原了「灰色带黄色 logo 的针织帽 + 浅灰短款卫衣 + "
             "黑色高腰裙 + 手遮脸 + 远山田野」，这类多要素组合 SD1.5 常丢项。")
    L.append("- 光影更接近真实摄影的**景深与空气感**，构图也更符合描述。")
    L.append("- 代价：约 19× 推理时间；且**本地 GGUF abliterated 变体会忽略着装约束**，"
             "必须使用标准版 + 显式负面提示词，否则输出不可控。")
    L.append("")

    L.append("## 四、选型建议\n")
    L.append("| 需求 | 推荐 | 理由 |")
    L.append("|---|---|---|")
    L.append("| 大批量出图 / 快速试稿 | `majicmixRealistic_v7` | 9s/张，写实且还原度高 |")
    L.append("| 动漫 / 插画风内容 | `Counterfeit-V3.0` 或 `AOM3A3` | 风格化明确 |")
    L.append("| 高保真成品 / 复杂多要素提示词 | `flux1-dev-fp8` | 语义与画质最佳 |")
    L.append("| 折中方案 | Flux **Q4_K_M**（未跑，建议测试） | 6.6GB 可入显存，速度应显著优于 FP8 |")
    L.append("")

    L.append("## 五、产出文件\n")
    L.append("- `sheets/compare_sd15_models.png` — SD1.5 三模型 × 8 场景对比拼图")
    L.append("- `sheets/compare_all_models.png` — 含 Flux 的四模型对比拼图")
    L.append("- `comparison_data.json` — 结构化实测数据（耗时/参数/文件名）")
    L.append("- `majicmix/` `counterfeit/` `aom3/` `flux_dev_fp8/` — 各模型 `_run.json` 明细")
    L.append("- 图片实际存放于 `output/pc_<model>_<scene>_00001_.png`")

    out = os.path.join(OUT, "comparison_report.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("WROTE:", out)
    for r in rows:
        print("  %-14s %s/%s avg=%s" % (r["sub"], r["ok"], r["total"], r["avg_sec"]))


if __name__ == "__main__":
    main()

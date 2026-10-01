# -*- coding: utf-8 -*-
"""
run_h3_guard_v5.py — H3 人物迁移「面部锁定 + 动作迁移」优化方案 v5
====================================================================

针对 daily_work_report_2026_09_21.md 暴露的问题，本脚本给出 5 个可运行的独立方案
（profile），共享同一套 H3 底座与同一套人脸后期链路，只在关键环节做正交增强。

问题 → 方案映射
---------------
| 报告中的问题 | 本方案对应解法 |
|---|---|
| ①「H3 空间切分丢帧/闪烁」（大动态甩头时空间切块接缝跳变） | **A** 换用「时间域 de-rope」：不切空间，切时间 |
| ②「H3 动作快时糊成一团」（快速动作被抹平） | **A** de-rope 慢放重绘，给模型更多时间相位 |
| ③「ReActor 逐帧独立 2D 漂移 → 五官微颤」 | **C** 面部独立链路 + 可调混合强度 + 遮罩羽化 |
| ④「CodeFormer 0.95 逐帧脑补 → 细节跳闪」 | **C** 把 `codeformer_weight` 降到 0.6~0.7（可扫参） |
| ⑤「动作太快、模型跟不上」 | **B** SLA 稀疏注意力省下的时间换成更多采样步数 |
| ⑥ 显存/效率 | 全部方案默认 turbo LoRA + 分块 FFN + Sage 注意力 |

Profile 一览
------------
- `base`      : 现网 C3 基线复刻（对照组，用于 A/B 量化）
- `derope`    : ★A 时间域 de-rope（对齐社区已验证的 Motion Lab 管线，保留 Motion Lab 的 jerk/jitter 抑制）
- `sla`       : ★B SLA 稀疏注意力 + 高步数（同样时间换更高保真，抑制采样噪声）
- `lock`      : ★C 面部独立链路（低权重 CodeFormer + 混合强度 + 羽化遮罩 + 可选遮罩合成）
- `full`      : ★D 组合拳 = derope + sla + lock（推荐）
- `quality`   : ★E 质量优先（fp16 视频 VAE + derope + lock + 更高步数）
- `upscale`   : ★F 低显存质量优先 = 0.5MP 生成 → 潜空间放大到 ~1.0MP（补报告"高画质"诉求）

用法
----
    # 列出所有 profile 及说明
    python run_h3_guard_v5.py --list

    # 环境自检（不动 GPU）
    python run_h3_guard_v5.py --check

    # 只导出工作流 JSON，不提交
    python run_h3_guard_v5.py --profile derope --save-only

    # 跑一个方案
    python run_h3_guard_v5.py --profile full --video shiling_dance_wave.mp4 --char characters/v3/C01_FACE_FRONT.png

    # 跑全部方案并出对比报告（耗时较长，建议先跑短片段）
    python run_h3_guard_v5.py --profile all --length 73 --report

    # 只对已有产物做质检对比
    python run_h3_guard_v5.py --measure-only --videos a.mp4 b.mp4 --report
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import h3_rope_common as C  # noqa: E402

BASE = C.BASE

# ---------------------------------------------------------------------------
# 资产名（ComfyUI 枚举里的相对名，已用 /object_info 核实）
# ---------------------------------------------------------------------------
UNET_REF2VA = "minimax_h3_ref2va_pruned_int8_convrot.safetensors"
TE_NVFP4 = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
VAE_VFP16 = "minimax_h3_video_vae_fp16.safetensors"
VAE_VINT8 = "minimax_h3_video_vae_int8_convrot.safetensors"
VAE_AUDIO = "minimax_h3_audio_vae_fp32.safetensors"
LORA_TURBO = "minimax_h3_turbo_4step_comfyui_pruned.safetensors"
LORA_TURBO_T8 = "minimax_h3_turbo_4step_ckpt500_comfyui_T8.safetensors"

# ★诊断开关：是否插入 MiniMaxLowVRAMAttention 补丁。
#   该节点标称「不改数学、输出与未打补丁一致」，但实测在 full 档下产物**全黑**
#   （73 帧 mean/std 全为 0，ReActor 报 "No faces found"）。
#   保留开关以便 A/B 定位；默认关闭，等确认兼容后再启用。
_LOWVRAM_ATTN = False
LORA_V4 = "minimax_h3_turbo_v4_step600_ema_pruned_comfyui.safetensors"


# ---------------------------------------------------------------------------
# 提示词
# ---------------------------------------------------------------------------
def build_prompt(subject_desc=None, scene_desc=None, motion_desc=None):
    """
    按 H3 官方结构书写。
    关键点（依据 TUNING.md 的 reference rule）：当图里有**强参考图**时，
    inject 可以提高而不会身份漂移，因为身份由参考图承载。
    所以提示词要把"身份完全来自 <Picture 1>"写死，让模型不去自己发明脸。
    """
    subject_desc = subject_desc or (
        "the young woman shown in <Picture 1>, with long dark wavy hair and "
        "delicate front bangs, refined almond-shaped eyes, clear porcelain skin, "
        "and a slender hourglass figure"
    )
    scene_desc = scene_desc or (
        "a bright indoor studio with soft even daylight and a clean neutral wall"
    )
    motion_desc = motion_desc or (
        "performing the dance of <Video 1> in full, hips swaying rhythmically "
        "and arms moving through the full range of the choreography"
    )
    return """subject_definitions:
<Subject 1> is {subject}. Her face, hairstyle and body figure are taken from <Picture 1> and stay identical in every frame.
<Video 1> is the source motion reference: it supplies the dance choreography, the timing, the torso turns and the arm gestures.

summary:
[reference generation + video editing] The target video recreates the continuous dance performance from <Video 1>, replacing the performer with <Subject 1>. The subject is placed in {scene}.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - her facial features, eye shape, nose, mouth, long dark wavy hair with front bangs and her body proportions are all fully preserved and identical to <Picture 1> in every single frame.
<Video 1> (motion structure): fully_preserved - the complete dance choreography, the exact number of beats, the arm gestures and the bodily rhythm are replicated exactly, with no added or removed beats.

detailed_description:
[Shot 1] Photorealistic cinematic vertical portrait video. A medium full-length shot frames <Subject 1> {motion}, in {scene}. Her long dark wavy hair with neat front bangs moves naturally with her head. Her expression is calm and confident, looking toward the camera. Skin shows fine realistic pore-level texture. The camera is locked off and steady; there is no camera shake.

overall_soundscape:
Soft ambient room tone and the faint rustle of fabric.

non_diegetic_music:
N/A""".format(subject=subject_desc, scene=scene_desc, motion=motion_desc)


# ---------------------------------------------------------------------------
# Profile 定义
# ---------------------------------------------------------------------------
# 说明：所有 profile 共用的底座参数
DEFAULTS = dict(
    width=448, height=768, length=73, fps=24.0,
    seed=42,
)

PROFILES = {
    "base": dict(
        title="对照组基线（复刻现网 C3）",
        desc="忠实复刻 daily_report 里的 run_h3_shiling_c3 结构：单次 Ref2VA + 4 步 res_multistep "
             "+ ReActor(YOLOv5l, codeformer 0.95)。仅用于 A/B 对照，不是优化方案。",
        layers=["core", "derive_c_lock"],
        guider="native",     # 用 Ref2VA 自带的采样链路
        steps=4,
        sampler="res_multistep",
        scheduler="simple",
        turbo=False,
        inject=None,
        derope=False,
        sla=False,
        swap=dict(enabled=True, detect="YOLOv5l", restore="codeformer.pth",
                  weight=0.95, visibility=1.0),
    ),

    "derope": dict(
        title="★A 时间域 de-rope（动作用力/闪烁主解法）",
        desc="用 ComfyUI-MAINodes「Motion Lab」的时间域方案替代空间切块：快速动作帧被保持(dilate)后"
             "以部分降噪重绘，再按 hold_map 精确取回原帧率。社区实测可把'空中转体糊成一团'变成清晰动作，"
             "同时因为重绘是**时序扩散**（H3 注意力本身带时序建模），不引入逐帧独立抖动。",
        layers=["core", "derive_a_derope"],
        guider="custom",
        pass1=dict(steps=12, scheduler="linear_quadratic", sampler="gradient_estimation",
                   turbo=True, turbo_strength=1.0),
        pass2=dict(steps=6, scheduler="beta", sampler="gradient_estimation",
                   inject=0.48, turbo=True, turbo_strength=1.0),
        oracle=dict(q=0.75, d_max=4, ramp=True, bridge=8, preset="balanced (default)"),
        smear=dict(dilation=4, expand_to_end=True),
        v2v=dict(audio_mode="follow the original performance (0.5)", audio_strength=0.5),
        derope=True, sla=False,
        swap=dict(enabled=True, detect="YOLOv5l", restore="codeformer.pth",
                  weight=0.60, visibility=0.85),
    ),

    "sla": dict(
        title="★B SLA 稀疏注意力 + 高步数提保真",
        desc="H3SLAAttention 跳过 90% 的 key block（实测 1.4~1.75x 加速，官方在一个 5090 上 44s/it→25s/it），"
             "把省下的时间换成 18~20 步采样。注意官方结论：**H3 的语音/细节伪影由步数驱动，不是 sparsity 驱动**，"
             "所以应该'提步数'而不是'降 sparsity'。dense_last_steps=2 让最后两步走全注意力，"
             "把'最终那一步的误差'补回来——这一步对画质最关键。",
        layers=["core", "derive_b_sla"],
        guider="native",
        sla=dict(sparsity_ratio=0.90, block_size=64, min_seq_len=8192,
                 dense_last_steps=2, protect_audio=True, enabled=True),
        steps=18,
        sampler="res_multistep",
        scheduler="simple",
        turbo=False,
        swap=dict(enabled=True, detect="YOLOv5l", restore="codeformer.pth",
                  weight=0.65, visibility=0.9),
    ),

    "lock": dict(
        title="★C 面部独立链路（人脸锁定/抑制闪烁）",
        desc="针对报告里诊断的两大闪烁机理逐条出手：\n"
             "  (1) CodeFormer 逐帧独立脑补 → 把权重从 0.95 降到 0.65、visibility 降到 0.85，"
             "让它'少发明、多信原图'；\n"
             "  (2) ReActor 逐帧 2D 漂移 → 用 ReActorOptions 的 "
             "restore_swapped_only=True 只修复换过的那张脸（避免把周围皮肤也一起重绘），"
             "并换成 ReActorFaceSwapOpt 让参数更干净；\n"
             "  (3) 可选：用 SAM(face_yolov8m) 抠出脸部区域 + 大羽化(24) 混合，"
             "让换脸边界在时间上更软，消除'贴片感/边界跳'。",
        layers=["core", "derive_c_lock"],
        guider="native",
        steps=8,
        sampler="res_multistep",
        scheduler="simple",
        turbo=False,
        swap=dict(enabled=True, detect="YOLOv5l", restore="codeformer.pth",
                  weight=0.65, visibility=0.85, restore_swapped_only=True,
                  soft_blend=False, feather=24, grow=6),
    ),

    "full": dict(
        title="★★D 组合拳（推荐主力 · 本机默认档）",
        desc="derope(时序去抖) + lock(面部锁定) 叠加。\n"
             "分工：derope 解决'快动作糊'并保持时序一致；lock 收尾把脸钉死。\n"
             "⚠️ 刻意**不含 SLA**：H3SLAAttention 的真实稀疏路径只在 engine='triton' 时启用，"
             "而本机未装 triton。本档保证开箱即跑，不引入无法满足的依赖。\n"
             "⚠️ 也**不含 MiniMaxLowVRAMAttention**：该节点标称'不改数学'，但实测在本机"
             "会让产物全黑（73 帧 mean/std 全为 0，ReActor 报 'No faces found'）。"
             "省显存改由 MiniMaxChunkFeedForward 承担。\n"
             "若日后装了 triton，可改跑 --profile sla 拿到 1.4~1.75x 加速。",
        layers=["core", "derive_a_derope", "derive_c_lock"],
        guider="custom",
        pass1=dict(steps=12, scheduler="linear_quadratic", sampler="gradient_estimation",
                   turbo=True, turbo_strength=1.0),
        pass2=dict(steps=6, scheduler="beta", sampler="gradient_estimation",
                   inject=0.48, turbo=True, turbo_strength=1.0),
        oracle=dict(q=0.75, d_max=4, ramp=True, bridge=8, preset="balanced (default)"),
        smear=dict(dilation=4, expand_to_end=True),
        v2v=dict(audio_mode="follow the original performance (0.5)", audio_strength=0.5),
        derope=True, sla=False,
        swap=dict(enabled=True, detect="YOLOv5l", restore="codeformer.pth",
                  weight=0.65, visibility=0.85, restore_swapped_only=True,
                  soft_blend=False, feather=24, grow=6),
    ),

    "quality": dict(
        title="★E 质量优先（fp16 VAE + 高步数）",
        desc="3 个质量档位全开：\n"
             "  - 视频 VAE 用 fp16（4.85GB）而不是 int8_convrot（2.95GB）——int8 VAE 解码快 1.5x 但"
             "有量化损失，成品推荐 fp16；\n"
             "  - pass1 保持 12 步 turbo（快），pass2 走 25 步**非 turbo 裸模型**（质量最高的一条路，"
             "官方文档明确说'pipeline 是给 keeper 用的'）；\n"
             "  - 面部用 lock 档同款低权重链路。\n"
             "代价：明显更慢，适合最终成品。",
        layers=["core", "derive_a_derope", "derive_c_lock"],
        guider="custom",
        pass1=dict(steps=12, scheduler="linear_quadratic", sampler="gradient_estimation",
                   turbo=True, turbo_strength=1.0),
        pass2=dict(steps=25, scheduler="beta", sampler="gradient_estimation",
                   inject=0.70, turbo=False, turbo_strength=1.0),
        oracle=dict(q=0.75, d_max=4, ramp=True, bridge=8, preset="balanced (default)"),
        smear=dict(dilation=4, expand_to_end=True),
        v2v=dict(audio_mode="follow the original performance (0.5)", audio_strength=0.5),
        derope=True, sla=False,
        vae_video=VAE_VFP16,
        swap=dict(enabled=True, detect="YOLOv5l", restore="codeformer.pth",
                  weight=0.65, visibility=0.85, restore_swapped_only=True,
                  soft_blend=False, feather=24, grow=6),
    ),

    "upscale": dict(
        title="★F 低显存质量优先（0.5MP 生成 → 潜空间放大）",
        desc="本机 16GB 显存跑 1.0MP 的 73 帧会非常吃力（官方测：32GB 卡跑 5s 片段的重绘 pass 就要 ~30GB）。\n"
             "所以这条路的思路是'小图生成、大图出片'：\n"
             "  - 生成阶段用 0.5MP（本机舒适区）；\n"
             "  - 用 H3LatentUpscale 把**潜空间**放大到 ~1.0MP 再解码——比像素域放大保留更多真实细节；\n"
             "  - 面部链路放最后，在放大后的高分辨率上换脸，脸的清晰度直接受益。",
        layers=["core", "derive_a_derope", "derive_c_lock"],
        guider="custom",
        width=384, height=640,
        upscale_to=dict(width=576, height=1024),
        pass1=dict(steps=12, scheduler="linear_quadratic", sampler="gradient_estimation",
                   turbo=True, turbo_strength=1.0),
        pass2=dict(steps=8, scheduler="beta", sampler="gradient_estimation",
                   inject=0.48, turbo=True, turbo_strength=1.0),
        oracle=dict(q=0.75, d_max=3, ramp=True, bridge=8, preset="balanced (default)"),
        smear=dict(dilation=4, expand_to_end=False),
        v2v=dict(audio_mode="follow the original performance (0.5)", audio_strength=0.5),
        derope=True,
        sla=dict(sparsity_ratio=0.90, block_size=64, min_seq_len=8192,
                 dense_last_steps=1, protect_audio=True, enabled=True),
        swap=dict(enabled=True, detect="YOLOv5l", restore="codeformer.pth",
                  weight=0.65, visibility=0.85, restore_swapped_only=True,
                  soft_blend=False, feather=24, grow=6),
    ),
}


# ---------------------------------------------------------------------------
# 图构建工具
# ---------------------------------------------------------------------------
class Graph:
    """极简 API 图构建器：自动分配节点 id。

    ⚠️ 这里有一个曾经踩过的坑（务必保留注释）：
    ComfyUI 的 `SamplerCustomAdvanced`（以及其它"输入是 LATENT 之类链路"的节点）
    在 validation 阶段会拿输入值做 dict key / set 成员。如果我们把已经包好的链路
    再包一层（`[["11", 1], 0]` 而不是 `["11", 1]`），它会在
    `exception_during_inner_validation` 里抛 `unhashable type: 'list'`——
    报错节点是 SamplerCustomAdvanced，但**真凶是构造链路的人**。
    所以 `add()` 里统一做一次"链路归一化"：只要是
    `[str_or_int, int]` 之外还嵌了一层 list 的，就取内层。
    """

    def __init__(self):
        self.g = {}
        self._n = 0

    @staticmethod
    def _norm_link(v):
        """把 [["11",1], 0] 这种双层嵌套压回 ["11",1]。"""
        if (isinstance(v, list) and len(v) == 2
                and isinstance(v[0], list) and len(v[0]) == 2
                and isinstance(v[0][0], (str, int)) and isinstance(v[0][1], int)):
            return v[0]
        return v

    def add(self, class_type, inputs=None, title=None):
        self._n += 1
        nid = str(self._n)
        fixed = {}
        for k, v in (inputs or {}).items():
            fixed[k] = self._norm_link(v)
        node = {"class_type": class_type, "inputs": fixed}
        if title:
            node["_meta"] = {"title": title}
        self.g[nid] = node
        return nid

    def out(self, nid, slot=0):
        return [nid, slot]


def _loaders(g, *, vae_video=VAE_VFP16, te=TE_NVFP4, weight_dtype="default"):
    n_unet = g.add("UNETLoader", {
        "unet_name": UNET_REF2VA, "weight_dtype": weight_dtype}, "Ref2VA int8 DiT")
    n_te = g.add("CLIPLoader", {
        "clip_name": te, "type": "minimax", "device": "default"}, "Qwen3-VL TE (nvfp4)")
    n_vv = g.add("VAELoader", {"vae_name": vae_video}, "video VAE")
    n_av = g.add("VAELoader", {"vae_name": VAE_AUDIO}, "audio VAE")
    return n_unet, n_te, n_vv, n_av


def _resolve_loaders(g, *, vae_video=VAE_VFP16, te=TE_NVFP4):
    """
    关键：本机只有 3 个可用底模，它们是**不同的文件**：

      - `minimax_h3_ref2va_pruned_int8_convrot` = Ref2VA 权重（带参考图条件，用于 Ref2VA）
      - `minimax_h3_fused_refdelta_r1024_turbo8_mystic07_int8_convrot` = **已融合 turbo 权重**的 Ref2VA

    报告的 C3 用的是 fused 版（turbo 已烘焙进去）；官方 Motion Lab 示例用的是裸
    ref2va + 外挂 turbo LoRA 两条 pass。

    >> 一条实测教训（务必保留）<<
    派生图（de-rope 两遍）里 pass1 / pass2 给**各一个独立的 UNETLoader 节点**，
    两个节点指向同一个文件。原因不是 ComfyUI 的限制（同一 UNETLoader 输出分叉到
    两条补丁链是完全合法的），而是为了让图更清晰："哪个 UNET 喂了哪条 pass"一眼可见，
    排障时不用回溯共享节点。权重只会被加载一次（缓存命中），不额外吃显存。
    """
    def _one():
        n_unet = g.add("UNETLoader", {
            "unet_name": UNET_REF2VA, "weight_dtype": "default"}, "Ref2VA int8 DiT")
        return n_unet

    n_unet_a = _one()
    n_unet_b = _one()
    n_te = g.add("CLIPLoader", {
        "clip_name": te, "type": "minimax", "device": "default"}, "Qwen3-VL TE (nvfp4)")
    n_vv = g.add("VAELoader", {"vae_name": vae_video}, "video VAE")
    n_av = g.add("VAELoader", {"vae_name": VAE_AUDIO}, "audio VAE")
    return n_unet_a, n_unet_b, n_te, n_vv, n_av


def _model_chain(g, n_unet, prof, *, turbo=True, turbo_strength=1.0):
    """
    标准的 H3 底座补丁链（顺序对显存与正确性都很重要）：
      UNET → LowVRAM 注意力(省峰值显存) → ChunkFeedForward → [SLA] → [LoRA]

    ★ 关于注意力补丁的选择（本机硬约束，勿改回去）：
      官方 ref2va example 用的是
        PathchSageAttentionKJ(sage_attention="auto")
          → MiniMaxH3MemoryEfficientSageAttentionPatch
      但这两个节点都**硬依赖 sageattention 包**：
        - PathchSageAttentionKJ 直接 `from sageattention import sageattn`，缺包即抛
          ModuleNotFoundError（本机实测：任务在节点 6 崩掉，prompt 直接失败）
        - MiniMaxH3MemoryEfficientSageAttentionPatch 在 _cuda_archs is None 时
          raise RuntimeError("sageattention is not new enough version...")
      本机 **triton 与 sageattention 均未安装**，所以这两个节点用不了。

      改用 `MiniMaxLowVRAMAttention`（KJNodes，minimax_nodes.py）：
        - 作者原话：把注意力调用按 head 分组切块，让 kernel 内部临时量
          （int8 q/k 副本、fp32 累加器）随分块数缩小，并在用完后立即释放
          qkv 缓冲与 normed block input；
        - **"without changing the math" / "Output is identical to the unpatched model"**
          —— 零数学改动、零画质代价，纯省峰值显存；
        - **不依赖任何外部包**，本机可用。
      对 16GB 卡来说这是严格更优的选择：既省显存，又不引入画质变量。

    SLA（H3SLAAttention）官方说"放在 MODEL 线上任意位置"，我们放在 ChunkFF 之后、
    LoRA 之前，这样 LoRA 的增量不会被稀疏注意力误伤。
    ⚠️ 但 SLA 的真实稀疏路径（block_sparse_attention）**只在 engine="triton" 时启用**，
    而本机没有 triton → 该 profile 目前只能作为"装了 triton 之后"的预留档。
    """
    cur = n_unet
    if _LOWVRAM_ATTN:
        cur = g.add("MiniMaxLowVRAMAttention", {
            "model": g.out(cur),
            "head_chunks": int(prof.get("head_chunks", 4))},
            "LowVRAM 注意力 (不改数学·省峰值显存)")
    cur = g.add("MiniMaxChunkFeedForward", {
        "model": g.out(cur),
        "chunks": int(prof.get("ff_chunks", 4)),
        "seq_threshold": int(prof.get("ff_seq_threshold", 4096))},
        "Chunk FFN (分块前馈)")
    # ★★ MiniMaxH3SigmaShift —— 绝不能省！
    # H3 是「视频+音频」联合扩散，视频与音频两条分支的最优噪声调度尺度不同
    # （实测 shift_video=12.0 / shift_audio=3.0）。不做 sigma shift 时，
    # 采样器拿到的 sigmas 与 H3 训练时的分布不匹配 → 产物**全黑**
    # （73 帧 mean/std 全为 0）。这是本机踩过的最大一个坑。
    # 依据：已验证可用的 tools/run_h3_shiling_c3.py 中同样有该节点。
    cur = g.add("MiniMaxH3SigmaShift", {
        "model": g.out(cur),
        "shift_video": float(prof.get("shift_video", 12.0)),
        "shift_audio": float(prof.get("shift_audio", 3.0))},
        "H3 Sigma Shift (视频/音频调度对齐)")

    if prof.get("sla"):
        s = prof["sla"]
        cur = g.add("H3SLAAttention", {
            "model": g.out(cur),
            "sparsity_ratio": float(s.get("sparsity_ratio", 0.90)),
            "block_size": str(s.get("block_size", 64)),
            "chunk_size": 8192,
            "pad_to": 0,
            "min_seq_len": int(s.get("min_seq_len", 12228)),
            "dense_last_steps": int(s.get("dense_last_steps", 2)),
            "protect_audio": bool(s.get("protect_audio", True)),
            "apply_to_self": True,
            "apply_to_cross": True,
            "stabilize_motion": bool(s.get("stabilize_motion", False)),
            "reference_protection": s.get("reference_protection", "Off"),
            "tail_correction": bool(s.get("tail_correction", False)),
            "use_int8_qk": True,
            "engine": s.get("engine", "comfy_kitchen"),
            "dense_backend": s.get("dense_backend", "comfy_kitchen"),
            "disable_fp16_accum": True,
            "enabled": bool(s.get("enabled", True)),
        }, "★H3 SLA 稀疏注意力")

    if turbo:
        cur = g.add("LoraLoaderModelOnly", {
            "model": g.out(cur), "lora_name": LORA_TURBO,
            "strength_model": float(turbo_strength)}, "turbo 4-step LoRA")
    return cur


def _vae_patches(g, cur):
    """SLA 之后接 SigmaShift（视频/音频噪声位移），保持 C3 的既有取值。"""
    return g.add("MiniMaxH3SigmaShift", {
        "model": g.out(cur), "shift_video": 12.0, "shift_audio": 3.0},
        "SigmaShift")


def _sampler(g, model, cond, latent, *, steps, scheduler, sampler, seed, title="",
             latent_slot=1):
    """
    latent / cond 收 **节点 id**（字符串），而不是包好的链路。
    这样调用方不会误包两层（见 Graph.add 的注释）。

    latent_slot 默认 1：`MiniMaxH3ReferenceToVideo` 的输出是
      slot0 = CONDITIONING (positive), slot1 = LATENT
    所以喂给采样的初始 latent 必须取 slot 1。
    """
    n_sig = g.add("BasicScheduler", {
        "model": g.out(model), "scheduler": scheduler,
        "steps": int(steps), "denoise": 1.0}, "scheduler %s/%s" % (scheduler, steps))
    n_gui = g.add("BasicGuider", {
        "model": g.out(model), "conditioning": g.out(cond)}, "guider")
    n_smp = g.add("KSamplerSelect", {"sampler_name": sampler}, "sampler " + sampler)
    n_noi = g.add("RandomNoise", {"noise_seed": int(seed)}, "noise")
    n_sample = g.add("SamplerCustomAdvanced", {
        "noise": g.out(n_noi), "guider": g.out(n_gui), "sampler": g.out(n_smp),
        "sigmas": g.out(n_sig), "latent_image": g.out(latent, latent_slot)},
        title or "sample")
    return n_sample


def _face_chain(g, n_images, swap, *, title_suffix=""):
    """
    面部链路（可插拔、可降级）。
    始终输出 (n_final_images, n_swapped_only_images)
    """
    if not swap or not swap.get("enabled"):
        return n_images, None

    n_ref = g.add("LoadImage", {"image": swap.get("char", "characters/v3/C01_FACE_FRONT.png")},
                  "face ref" + title_suffix)

    n_opts = g.add("ReActorOptions", {
        "input_faces_order": "large-small",
        "input_faces_index": "0",
        "detect_gender_input": "no",
        "source_faces_order": "large-small",
        "source_faces_index": "0",
        "detect_gender_source": "no",
        "console_log_level": 1,
        "restore_swapped_only": bool(swap.get("restore_swapped_only", True)),
    }, "ReActor options (帧间稳定)")

    n_sw = g.add("ReActorFaceSwapOpt", {
        "enabled": True,
        "input_image": g.out(n_images),
        "source_image": g.out(n_ref),
        "swap_model": "inswapper_128.onnx",
        "facedetection": swap.get("detect", "YOLOv5l"),
        "face_restore_model": swap.get("restore", "codeformer.pth"),
        "face_restore_visibility": float(swap.get("visibility", 0.85)),
        "codeformer_weight": float(swap.get("weight", 0.65)),
        "options": g.out(n_opts),
    }, "★ReActorFaceSwapOpt" + title_suffix)

    n_swapped = g.out(n_sw, 0)

    if not swap.get("soft_blend"):
        return n_sw, n_sw

    # ---- 可选：软羽化混合（抑制"贴片感"与边界跳）
    # 思路：用 ReActorMaskHelper 抠出脸部区域 → GrowMaskWithBlur 大幅羽化 →
    #       ImageCompositeMasked 把"已换脸"叠回"原始序列"。
    # 这样只有脸被替换，且边界是软过渡，时间上更顺。
    n_mh = g.add("ReActorMaskHelper", {
        "image": g.out(n_images),
        "swapped_image": g.out(n_sw),
        "bbox_model_name": "bbox/face_yolov8m.pt",
        "bbox_threshold": 0.5,
        "bbox_dilation": int(swap.get("grow", 6)),
        "bbox_crop_factor": 3.0,
        "bbox_drop_size": 10,
        "sam_model_name": "sam_vit_b_01ec64.pth",
        "sam_dilation": 0,
        "sam_threshold": 0.93,
        "bbox_expansion": 0,
        "mask_hint_threshold": 0.7,
        "mask_hint_use_negative": "False",
        "morphology_operation": "dilate",
        "morphology_distance": 0,
        "blur_radius": int(swap.get("feather", 24)),
        "sigma_factor": 1.0,
    }, "ReActor mask helper (脸部区域+羽化)")

    n_masked = g.add("ImageCompositeMasked", {
        "destination": g.out(n_images),
        "source": g.out(n_sw),
        "mask": g.out(n_mh, 1),
        "x": 0, "y": 0, "resize_source": False,
    }, "★软羽化合成 (只换脸)")
    return n_masked, n_sw


# ---------------------------------------------------------------------------
# 各 profile 的图
# ---------------------------------------------------------------------------
def build_base(prof, *, video, char, bg=None, width, height, length, seed,
               prompt=None, fps=24.0, prefix="h3_base"):
    g = Graph()
    n_unet, n_te, n_vv, n_av = _loaders(g)
    cur = _model_chain(g, n_unet, prof, turbo=bool(prof.get("turbo")))
    cur = _vae_patches(g, cur)

    n_vid = g.add("VHS_LoadVideo", {
        "video": video, "force_rate": float(fps),
        "custom_width": int(width), "custom_height": int(height),
        "frame_load_cap": int(length), "skip_first_frames": 0,
        "select_every_nth": 1, "format": "AnimateDiff"}, "source video")
    n_ref = g.add("LoadImage", {"image": char}, "character ref")

    refs = {"clip": g.out(n_te), "vae": g.out(n_vv), "audio_vae": g.out(n_av),
            "prompt": prompt, "width": int(width), "height": int(height),
            "length": int(length), "ref_image_size": "match",
            "ref_images.ref_image_0": g.out(n_ref),
            "ref_videos.ref_video_0": g.out(n_vid)}
    if bg:
        n_bg = g.add("LoadImage", {"image": bg}, "background ref")
        refs["ref_images.ref_image_1"] = g.out(n_bg)

    n_cond = g.add("MiniMaxH3ReferenceToVideo", refs, "Ref2VA conditioning")

    n_smp = _sampler(g, cur, n_cond, n_cond,
                     steps=prof["steps"], scheduler=prof["scheduler"],
                     sampler=prof["sampler"], seed=seed, title="pass (single)")

    n_img = g.add("VAEDecode", {"samples": g.out(n_smp), "vae": g.out(n_vv)},
                  "video decode")
    n_aud = g.add("VAEDecodeAudio", {"samples": g.out(n_smp), "vae": g.out(n_av)},
                  "audio decode")

    n_final, n_swapped = _face_chain(g, n_img, dict(prof.get("swap") or {}, char=char))

    n_v = g.add("CreateVideo", {"images": g.out(n_final), "audio": g.out(n_aud),
                                "fps": float(fps), "bit_depth": 8}, "create video")
    g.add("SaveVideo", {"video": g.out(n_v), "format": "auto", "codec": "auto",
                        "filename_prefix": C.rel_prefix("h3_guard", prefix)},
          "save")
    # 同时存一份"仅换脸未羽化"的版本，方便对比羽化的影响
    if n_swapped is not None:
        n_v2 = g.add("CreateVideo", {"images": g.out(n_swapped),
                                     "audio": g.out(n_aud),
                                     "fps": float(fps), "bit_depth": 8},
                     "create video (swapped-only)")
        g.add("SaveVideo", {"video": g.out(n_v2), "format": "auto", "codec": "auto",
                            "filename_prefix": C.rel_prefix("h3_guard", prefix + "_noswblend")},
              "save (swapped-only)")
    return g.g


def build_derope(prof, *, video, char, bg=None, width, height, length, seed,
                 prompt=None, fps=24.0, prefix="h3_derope"):
    """
    ★A/F 时间域 de-rope 两遍管线（对齐官方 motion_pipeline_ref2va_audioinit_api.json）：
      pass1: turbo 12 步生成 baseline
      oracle: 从 baseline latent 读 jerk，产出 hold_map
      smear : 按 hold_map 保持帧 -> dilated 序列
      v2vinit: 编码 dilated 序列为 H3 AV latent（带 audio seed）
      pass2: turbo 6 步 / inject 0.48 重绘
      recover: 按 hold_map 精确丢回原帧率（frame selection，非重采样）
    """
    g = Graph()
    n_unet_a, n_unet_b, n_te, n_vv, n_av = _resolve_loaders(
        g, vae_video=prof.get("vae_video", VAE_VFP16))
    m1 = _model_chain(g, n_unet_a, prof, turbo=prof["pass1"].get("turbo"),
                      turbo_strength=prof["pass1"].get("turbo_strength", 1.0))
    m2 = _model_chain(g, n_unet_b, prof, turbo=prof["pass2"].get("turbo"),
                      turbo_strength=prof["pass2"].get("turbo_strength", 1.0))

    n_vid = g.add("VHS_LoadVideo", {
        "video": video, "force_rate": float(fps),
        "custom_width": int(width), "custom_height": int(height),
        "frame_load_cap": int(length), "skip_first_frames": 0,
        "select_every_nth": 1, "format": "AnimateDiff"}, "source video")
    n_ref = g.add("LoadImage", {"image": char}, "character ref")

    refs = {"clip": g.out(n_te), "vae": g.out(n_vv), "audio_vae": g.out(n_av),
            "prompt": prompt, "width": int(width), "height": int(height),
            "length": int(length), "ref_image_size": "match",
            "ref_images.ref_image_0": g.out(n_ref),
            "ref_videos.ref_video_0": g.out(n_vid)}
    if bg:
        n_bg = g.add("LoadImage", {"image": bg}, "background ref")
        refs["ref_images.ref_image_1"] = g.out(n_bg)

    # ---- pass 1
    n_cond1 = g.add("MiniMaxH3ReferenceToVideo", refs, "Ref2VA conditioning (pass1)")
    p1 = prof["pass1"]
    n_s1 = _sampler(g, m1, n_cond1, n_cond1,
                    steps=p1["steps"], scheduler=p1["scheduler"],
                    sampler=p1["sampler"], seed=seed, title="★pass1 baseline")
    n_img1 = g.add("VAEDecode", {"samples": g.out(n_s1), "vae": g.out(n_vv)}, "baseline decode")
    n_aud1 = g.add("VAEDecodeAudio", {"samples": g.out(n_s1), "vae": g.out(n_av)}, "baseline audio")

    # 保留一份 baseline（对照组）
    n_vb = g.add("CreateVideo", {"images": g.out(n_img1), "audio": g.out(n_aud1),
                                 "fps": float(fps), "bit_depth": 8}, "baseline video")
    g.add("SaveVideo", {"video": g.out(n_vb), "format": "auto", "codec": "auto",
                        "filename_prefix": C.rel_prefix("h3_guard", prefix + "_pass1baseline")},
          "save pass1 baseline")

    # ---- oracle + smear
    o = prof["oracle"]
    n_oracle = g.add("H3JerkOracle", {
        "samples": g.out(n_s1), "length": int(length),
        "q": float(o["q"]), "d_max": int(o["d_max"]), "ramp": bool(o["ramp"]),
        "preset": o.get("preset", "balanced (default)"),
        "bridge": int(o["bridge"]), "profile_mode": o.get("profile_mode", "value |d3| (default)"),
        "fps": int(fps), "model_profile": "minimax-h3",
    }, "★H3 Jerk Oracle（找出快动作段）")

    sm = prof["smear"]
    n_smear = g.add("H3TimeSmear", {
        "images": g.out(n_img1), "dilation": int(sm["dilation"]),
        "hold_map": g.out(n_oracle, 0),
        "expand_to_end": bool(sm.get("expand_to_end", True)),
        "fps": int(fps),
    }, "★H3 Time Smear（慢放重绘）")

    n_enc = g.add("VAEEncode", {"pixels": g.out(n_smear), "vae": g.out(n_vv)},
                  "encode dilated")

    # 音频 seed：把 baseline 的音频按同样 hold_map 拉长后编码进 pass2
    n_asmear = g.add("H3AudioSmear", {
        "audio": g.out(n_aud1), "hold_map": g.out(n_smear, 1), "fps": int(fps)},
        "audio smear")
    n_aenc = g.add("VAEEncodeAudio", {"audio": g.out(n_asmear), "vae": g.out(n_av)},
                   "encode smeared audio")

    v2 = prof["v2v"]
    n_init = g.add("H3V2VInit", {
        "samples": g.out(n_enc),
        "audio_latent": g.out(n_aenc),
        "audio_mode": v2.get("audio_mode", "follow the original performance (0.5)"),
        "audio_strength": float(v2.get("audio_strength", 0.5)),
    }, "★H3 V2V Init（dilated 视频+音频 初始化）")

    # ---- pass 2
    n_cond2 = g.add("MiniMaxH3ReferenceToVideo", refs, "Ref2VA conditioning (pass2)")
    p2 = prof["pass2"]
    n_sig2 = g.add("H3InjectSchedule", {
        "model": g.out(m2), "scheduler": p2.get("scheduler", "beta"),
        "total_steps": int(p2["steps"]), "inject": float(p2["inject"]),
        "preset": p2.get("preset", "custom")}, "★H3 Inject Schedule")
    n_gui2 = g.add("BasicGuider", {"model": g.out(m2), "conditioning": g.out(n_cond2)},
                   "guider pass2")
    n_smp2 = g.add("KSamplerSelect", {"sampler_name": p2.get("sampler", "gradient_estimation")},
                   "sampler pass2")
    n_noi2 = g.add("RandomNoise", {"noise_seed": int(seed) + 1}, "noise pass2")
    n_s2 = g.add("SamplerCustomAdvanced", {
        "noise": g.out(n_noi2), "guider": g.out(n_gui2), "sampler": g.out(n_smp2),
        "sigmas": g.out(n_sig2), "latent_image": g.out(n_init)}, "★pass2 de-rope")
    n_img2 = g.add("VAEDecode", {"samples": g.out(n_s2), "vae": g.out(n_vv)}, "de-rope decode")
    n_aud2 = g.add("VAEDecodeAudio", {"samples": g.out(n_s2), "vae": g.out(n_av)}, "de-rope audio")

    # 可选：潜空间放大（profile upscale）
    if prof.get("upscale_to"):
        up = prof["upscale_to"]
        n_up = g.add("H3LatentUpscale", {
            "samples": g.out(n_s2), "scale": 1.0, "mode": "bilinear",
            "width": int(up["width"]), "height": int(up["height"])},
            "★H3 Latent Upscale -> %sx%s" % (up["width"], up["height"]))
        n_img2 = g.add("VAEDecode", {"samples": g.out(n_up, 0), "vae": g.out(n_vv)},
                       "decode upscaled")

    # ---- recover
    n_rec = g.add("H3ExactRecover", {
        "images": g.out(n_img2), "hold_map": g.out(n_smear, 1)},
        "★H3 Exact Recover（精确回到原帧率）")
    n_arec = g.add("H3AudioRecover", {
        "audio": g.out(n_aud2), "hold_map": g.out(n_smear, 1), "fps": int(fps),
        "reference": g.out(n_aud1), "reference_mix": 1.0,
        "audio_source": "keep the original performance (safe default)"},
        "★H3 Audio Recover")

    n_final, n_swapped = _face_chain(g, n_rec, dict(prof.get("swap") or {}, char=char))

    n_v = g.add("CreateVideo", {"images": g.out(n_final), "audio": g.out(n_arec),
                                "fps": float(fps), "bit_depth": 8}, "create video")
    g.add("SaveVideo", {"video": g.out(n_v), "format": "auto", "codec": "auto",
                        "filename_prefix": C.rel_prefix("h3_guard", prefix)},
          "★save de-rope")

    if n_swapped is not None:
        n_v2 = g.add("CreateVideo", {"images": g.out(n_swapped), "audio": g.out(n_arec),
                                     "fps": float(fps), "bit_depth": 8},
                     "create video (swapped-only)")
        g.add("SaveVideo", {"video": g.out(n_v2), "format": "auto", "codec": "auto",
                            "filename_prefix": C.rel_prefix("h3_guard", prefix + "_noswblend")},
              "save (swapped-only)")

    # 附：把 hold_map 吐到磁盘，方便质检时"跳过保持帧"公平比较
    g.add("H3SaveHoldMap", {
        "hold_map": g.out(n_smear, 1),
        "filename_prefix": C.rel_prefix("h3_guard", prefix + "_holdmap")},
        "save hold map")
    return g.g


def build_graph(profile: str, **kw):
    """
    构造某个 profile 的 API 工作流。
    注意：不要在这里写回全局 DEFAULTS（早期版本用 setdefault 直接改 kw 是安全的，
    但如果误改 DEFAULTS 会让 --profile all 的所有 run 都带上第一个 profile 的 width/height）。
    这里用一份浅拷贝兜底，保证调用方完全掌控。
    """
    prof = PROFILES[profile]
    merged = dict(DEFAULTS)
    merged.update(kw)               # 调用方显式传入的优先
    merged.setdefault("prompt", build_prompt())
    prefix = merged.pop("prefix", None) or ("h3_%s" % profile)
    # 显式传参要求：width/height/length/seed/fps/video/char 都必须有
    if prof.get("derope"):
        return build_derope(prof, prefix=prefix, **merged)
    return build_base(prof, prefix=prefix, **merged)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def do_check():
    info = C.object_info()
    ok, rep = C.check_assets(info)
    print("=" * 66)
    print("H3 人物迁移优化方案 v5 · 环境自检")
    print("=" * 66)
    print("ComfyUI 在线        : %s" % C.server_alive())
    print("节点总数            : %d" % len(info))
    print("产物根目录          : %s" % C.out_root())
    print("")
    print("节点检查（勾选的层）:")
    for layer, miss in (rep["nodes_missing"] or {}).items():
        print("  [%s] 缺失: %s" % (layer, ", ".join(miss)))
    if not rep["nodes_missing"]:
        print("  全部通过 ✔")
    print("")
    print("模型检查:")
    for k, v in sorted(rep["models"].items()):
        mark = "OK " if v else "缺失"
        print("  %-24s %s  %s" % (k, mark, v or "-"))
    print("")
    print("结论: %s" % ("可以做实验 ✔" if ok else "有缺项，请先补齐 ✘"))
    return ok


def do_list():
    print("=" * 78)
    print("H3 人物迁移优化方案 v5 · 可用 Profile")
    print("=" * 78)
    for k, v in PROFILES.items():
        print("")
        print("■ %-10s %s" % (k, v["title"]))
        for ln in (v["desc"] or "").split("\n"):
            print("    " + ln)
    print("")
    print("建议顺序: check -> base(对照) -> lock -> derope -> full -> quality/upscale")


def do_run(args, profile):
    prof = PROFILES[profile]
    print("=" * 78)
    print("Profile: %s  |  %s" % (profile, prof["title"]))
    print("=" * 78)

    ok, rep = C.check_assets()
    if not ok:
        print("[!] 资产自检未通过：")
        print(json.dumps(rep["nodes_missing"], ensure_ascii=False, indent=2))
        print("缺失模型:", rep["models_missing"])
        return None

    width = args.width or prof.get("width", DEFAULTS["width"])
    height = args.height or prof.get("height", DEFAULTS["height"])

    def _mk(pf, w, h, i):
        """每个 profile 用独立入口，避免 build_graph 内部 setdefault 污染全局 DEFAULTS。"""
        return build_graph(
            pf,
            video=args.video, char=args.char, bg=(args.bg or None),
            width=w, height=h, length=args.length, seed=args.seed + i,
            fps=args.fps, prefix=args.prefix or ("h3_%s" % pf),
        )

    graph = _mk(profile, width, height, 0)

    # 落盘（可交互导入 ComfyUI 检查）
    wf_dir = os.path.join(BASE, "workflows", "v5")
    os.makedirs(wf_dir, exist_ok=True)
    wf_path = os.path.join(wf_dir, "h3_guard_v5_%s_api.json" % profile)
    C.save_json(wf_path, graph)
    print("工作流已保存: %s  (%d 节点)" % (wf_path, len(graph)))

    if args.save_only:
        return graph

    ok2, pid = C.submit(graph)
    if not ok2:
        print("[X] 提交失败: %s" % pid)
        return None
    print("[√] 已提交, prompt_id = %s" % pid)

    t0 = time.time()

    def tick(el):
        if int(el) % 30 < 6:
            print("    ... 已运行 %.0fs" % el)

    done, outputs, el, err = C.wait(pid, timeout=args.timeout, on_tick=tick)
    print("")
    if not done:
        print("[X] 未完成: %s (耗时 %.1fs)" % (err, el))
        if args.auto_clear:
            print("    尝试中断并清空队列:", C.interrupt_and_clear())
        return None

    files = C.collect_videos(outputs)
    print("[√] 完成，耗时 %.1fs" % el)
    for f in files:
        print("    产物: %s" % f)

    # 记录 run log
    run = {
        "profile": profile, "title": prof["title"], "prompt_id": pid,
        "elapsed_s": round(el, 1), "files": files,
        "video": args.video, "char": args.char, "bg": args.bg,
        "width": width, "height": height, "length": args.length, "seed": args.seed,
        "fps": args.fps, "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    d = C.out_dir("h3_guard")
    logp = os.path.join(d, "_run_%s.json" % profile)
    prev = None
    if os.path.isfile(logp):
        try:
            with open(logp, encoding="utf-8") as fh:
                prev = json.load(fh)
        except Exception:
            prev = None
    if isinstance(prev, list):
        prev.append(run)
        run = prev
    C.save_json(logp, run)
    print("运行日志: %s" % logp)
    return {"run": run, "files": files}


def do_measure(args):
    """对已有视频做质检对比。"""
    vids = list(args.videos or [])
    # 若未指定，自动找当天产物
    if not vids:
        d = C.out_dir("h3_guard")
        for fn in sorted(os.listdir(d)):
            if fn.lower().endswith(".mp4") and "_holdmap" not in fn:
                vids.append(os.path.join(d, fn))
    if not vids:
        print("没有可测量的视频。用 --videos 指定。")
        return []
    print("测量 %d 个视频 ..." % len(vids))
    results = []
    for i, v in enumerate(vids):
        if not os.path.isfile(v):
            print("  跳过（不存在）: %s" % v)
            continue
        label = os.path.splitext(os.path.basename(v))[0]
        try:
            r = C.analyze_face_stability(v, max_frames=args.max_frames, label=label)
            results.append(r)
            print("  [%d/%d] %-52s det=%.3f id=%.4f jit=%s" % (
                i + 1, len(vids), label[:52], r["detect_rate"],
                -1 if r["identity"] is None else r["identity"],
                C.fmt(r["jitter_ratio"], 4)))
        except Exception as e:  # noqa: BLE001
            print("  失败 %s: %r" % (label, e))
    if not results:
        return []
    if args.report:
        d = C.out_dir("h3_guard")
        rp = C.write_report(os.path.join(d, "face_stability_report.md"), results,
                            meta={"视频数": len(results),
                                  "检测器": results[0].get("detector")})
        jp = C.save_json(os.path.join(d, "face_stability_data.json"), results)
        print("报告: %s" % rp)
        print("数据: %s" % jp)
        print("")
        for r in results:
            print("  %-46s jitter=%-9s identity=%-8s flicker=%s" % (
                r["label"][:46], C.fmt(r["jitter_ratio"], 4),
                C.fmt(r["identity"], 4), C.fmt(r["flicker_rate"], 4)))
    return results


def main():
    ap = argparse.ArgumentParser(
        description="H3 人物迁移「面部锁定 + 动作迁移」优化方案 v5",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="列出所有 profile")
    ap.add_argument("--check", action="store_true", help="环境与资产自检")
    ap.add_argument("--profile", default="full",
                    help="profile 名，或 all（跑全部）")
    ap.add_argument("--video", default="shiling_dance_wave.mp4", help="输入视频（input/ 下）")
    ap.add_argument("--char", default="characters/v3/C01_FACE_FRONT.png", help="人脸参考图")
    ap.add_argument("--bg", default=None, help="背景参考图（可选）")
    ap.add_argument("--width", type=int, default=0, help="覆盖宽度")
    ap.add_argument("--height", type=int, default=0, help="覆盖高度")
    ap.add_argument("--length", type=int, default=DEFAULTS["length"], help="帧数（17*N+5）")
    ap.add_argument("--fps", type=float, default=DEFAULTS["fps"], help="帧率")
    ap.add_argument("--seed", type=int, default=DEFAULTS["seed"], help="随机种子")
    ap.add_argument("--prefix", default=None, help="产物前缀")
    ap.add_argument("--timeout", type=int, default=5400, help="单次等待上限（秒）")
    ap.add_argument("--save-only", action="store_true", help="只导出工作流不提交")
    ap.add_argument("--auto-clear", action="store_true", default=True,
                    help="失败时自动中断并清空队列")
    ap.add_argument("--measure-only", action="store_true", help="只做质检，不生成")
    ap.add_argument("--videos", nargs="*", default=None, help="要质检的视频（可多个）")
    ap.add_argument("--max-frames", type=int, default=0, help="质检最多读多少帧")
    ap.add_argument("--report", action="store_true", help="生成对比报告")
    ap.add_argument("--lowvram-attn", dest="lowvram_attn", action="store_true",
                    default=None,
                    help="强制启用 MiniMaxLowVRAMAttention 补丁（A/B 诊断用）")
    ap.add_argument("--no-lowvram-attn", dest="lowvram_attn", action="store_false",
                    default=None,
                    help="强制关闭 MiniMaxLowVRAMAttention 补丁（A/B 诊断用）")
    args = ap.parse_args()

    # 诊断开关：命令行优先，否则用模块默认（当前默认关闭，见 _LOWVRAM_ATTN 注释）
    global _LOWVRAM_ATTN
    if args.lowvram_attn is not None:
        _LOWVRAM_ATTN = bool(args.lowvram_attn)
        print("[i] MiniMaxLowVRAMAttention = %s" % _LOWVRAM_ATTN)

    if args.list:
        do_list(); return
    if args.check:
        do_check(); return
    if args.measure_only:
        do_measure(args); return

    targets = list(PROFILES.keys()) if args.profile == "all" else [args.profile]
    for p in targets:
        if p not in PROFILES:
            print("未知 profile: %s（用 --list 查看）" % p)
            continue
        do_run(args, p)
        if len(targets) > 1:
            print("")

    if args.report:
        print("=" * 78)
        print("开始质检对比 ...")
        print("=" * 78)
        do_measure(args)


if __name__ == "__main__":
    main()

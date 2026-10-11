# AI 动漫短剧 · 本地化执行手册

> 把「创意 → 剧本 → 资产 → 分镜 → 视频」这套流程，落到**本机 ComfyUI（RTX 4060 Ti 16GB / Windows）**可跑的命令与目录约定。
> 生成日期 2026-10-10，已对照本机真实文件/脚本 CLI 校准，非泛泛而谈。
>
> 对应豆包那套工作流：本机没有豆包桌面版的 Skill 体系，所以用 **「目录约定 + `tools/_drama_gate.py` 路由闸门」** 来强制流程顺序（未过剧本阶段不许出图/出视频）。

---

## 0. 本机现状盘点（已实测枚举）

- **启动**：需手动 `python main.py --lowvram --listen 0.0.0.0 --port 8188`（anaconda3 的 python，约 20s，**不会自动启动**）
- **代理坑**：`os.environ` 代理（曾见 `127.0.0.1:16265`，旧记 21193 已过期）会劫持 `127.0.0.1:8188` → 本地 HTTP 用 `ProxyHandler({})` 绕代理（见 `_pc_common._OPENER`；详见 §6）
- **checkpoints 实际在盘**：`Juggernaut-XL_v9`、`RealVisXL_V4.0`（均为 SDXL 写实）、`v1-5-pruned-emaonly`（SD1.5 基础版）
- **⚠️ 无任何动漫底模**：`Counterfeit` / `AOM3` / `Animagine` / `majicmix_v7` 均**不在盘**（脚本 CONFIG 引用了它们但文件缺失）——这是做动漫短剧要补的**唯一硬缺口**
- **视频引擎**：H3（`minimax_h3_*` 3×19.5GB）✅、Wan2.2（17.1GB）✅、Z-Image Turbo ✅（0.9min/1024²）
- **工具链**：`_pc_*`（出图批处理）、`h3_*`（视频快线）、`faceswap_app`（音频）、`add_subtitles` / `restore_and_mix_audio` / `add_ai_watermark` / `prompt_safety_linter` ✅
- **一致性节点**：`ReActor` ✅；`IPAdapter_plus` ❌（禁用）→ 一致性靠 **种子锁 + 参考图 + H3 首帧 + ReActor 面部** 组合

---

## 1. 补一个动漫底模（唯一硬缺口）

方案任选其一（按性价比排序）：

- **A. Counterfeit-V3.0（SD1.5 动漫，★推荐）**：~4GB fp16。下完丢进 `models/checkpoints/Counterfeit-V3.0_fp16.safetensors`，`tools/_pc_gen_sd15.py` 的 CONFIG **已内置该名**，文件一到立即可用，且 SD1.5 在 16GB lowvram 上最稳最快。
- **B. Animagine XL V3（SDXL 动漫）**：分辨率更高、资产表更精细，但 SDXL ~55s/张偏慢。
- **C. 不补底模，用 Z-Image Turbo + 强风格词**：最快，但动漫味弱，只建议用于分镜草稿。
- 下载用统一下载器 `python tools/_dl_weights.py --set counterfeit`（已内置**断点续传 + 字节校验**，失败自动重下；残片权重会静默损坏成坏文件，故必须校验）

> 结论：选 **A**，最贴合现有 `_pc_*` 管线，且显存最安全。

---

## 2. 五步 × 本机资源映射

### Step 1 创意构思
- **工具**：豆包桌面版（需会员）/ 或本机 `bridge-llm` / `LLM-Session` 节点 / `blueprints/Prompt Enhance`
- **做法**：一句话梗概 → 让 LLM 扩成 3–5 集大纲（每集 60–90s）
- **交付**：`output/<date>/<proj>/00_concept/outline.md`

### Step 2 落地剧本（四要素：地点 / 角色 / 事件 / 情绪）
- **做法**：让 LLM 为每集产出四要素；**先冻结人物设定**（姓名 / 年龄 / 发型 / 服装 / 标志性道具），后面资产表照此生成
- **交付**：`00_concept/script_ep01.json`（schema 见 §5）

### Step 3 资产图设计（一致性核心）
**人物资产（每角色一张 turnaround sheet）**
- **规格**：正 / 侧 / 背 全身 512×768（SD1.5）或 1024×1536（SDXL）+ 头部特写 + 身高同框
- **引擎**：Counterfeit（SD1.5，方案 A）或 Animagine（SDXL，方案 B）
- **锁种子**：同一角色固定 master seed。⚠️ `_pc_*` 默认 `seed = sbase + i`（按场景自增），要锁角色需改 `tools/_pc_prompts.py` 或在 **UI 里手动锁 seed**
- **一致性增强**：种子锁 + 强角色描述 + 参考图 Canny 控制（`blueprints/ControlNet (Z-Image-Turbo)` + `sai_xl_canny_128lora`）
- **⚠️ 重要**：`_pc_gen_sd15.py` / `_pc_gen_zimage.py` 是**固定提示词批处理**（驱动 `tools/_pc_prompts.P.SCENES`），`--scenes` 只是筛已定义场景，**不是"生成任意角色"的通用工具**。要生成你的角色二选一：
  1. 在 `tools/_pc_prompts.py` 增你的场景/提示词后调用；或
  2. 直接在 ComfyUI UI 里用 Counterfeit 手动出图（更灵活，推荐新手）
- **交付**：`01_assets/char_<name>_sheet.png` + `char_ref.json`

**场景资产**
- **规格**：全景 1920×1080 + 地标特写 + 核心道具（如发光树洞，去背）
- **工具**：同上出图引擎；去背用 `blueprints/Remove Background (BiRefNet)`（BiRefNet 需分块 32 帧）
- **交付**：`01_assets/scene_<id>.png`、`prop_<id>.png`

### Step 4 分镜画面生成
- **做法**：用「角色参考图 + 场景参考图」作条件，逐镜生成关键帧（每镜 1–3 帧），先定稿静帧再进视频
- **引擎**：Z-Image Turbo（`_pc_gen_zimage.py`，最快）或 Counterfeit
- **闸门**：分镜帧须复用角色 master seed + 参考图；用 `tools/h3_rope_common` 的 `identity` 指标验相似度
- **交付**：`02_storyboard/shot_001.png …` + `storyboard.json`（§5）

### Step 5 视频生成与剪辑
**视频生成（本地主力 = H3）**
- 每镜用分镜关键帧作首帧（首帧锁定，类比豆包 Flow 的首帧挂载，本地用 H3 reference / `--first-frame`）：
  ```bash
  python tools/h3_fast_submit.py --prompt-file p.txt \
      --first-frame output/2026-10-10/<proj>/02_storyboard/shot_001.png \
      --width 736 --height 1088 --length 124 --seed 20260906
  ```
- 多段长镜衔接：
  ```bash
  python tools/h3_fast_segmented.py --segments 5 --seg-len 73 --width 736 --height 1088
  # 跳过生成只重拼：--merge-only
  ```
- **硬规则（项目记忆 F 区）**：必须 `MiniMaxH3SigmaShift`(shift_video=12 / shift_audio=3) 否则**产物全黑但任务"成功结束"**；视频 VAE 用 `fp16`；**禁用** `PatchSageAttentionKJ` / `MiniMaxH3MemoryEfficientSageAttentionPatch` / `MiniMaxLowVRAMAttention`（产物异常）
- **验帧**：每次渲染后读逐帧 mean/std 非全零。⚠️ `tools/_checkv.py` 当前**硬编码旧目录** `output/2026-09-22_wb/h3_guard`，勿直接套用；可复用 `tools/h3_rope_common` 自写校验
- **备选视频引擎**：Wan2.2（`blueprints/Image to Video (Wan 2.2)`）；Wan2.2-Animate 动作迁移 `length=49` 实测出 **53 帧**，需裁前 4 帧
- **参考样例**：`tools/h3_fashion_10pose_anime.py`（本机已有动漫姿态 H3 脚本，参数可直接照抄）

**后期剪辑（全用现有 tools）**
- 配音：本机 `edge_tts`（sherpa 技能是占位，不可用）
- 配乐：`blueprints/Audio Generation (Stable Audio 3 Medium)` / `Text to Audio (ACE-Step 1.5)`
- 音频合成：`tools/restore_and_mix_audio.py` + `tools/faceswap_app/core/audio_mixer.py`
- 字幕：`tools/add_subtitles.py`（ffmpeg drawtext，用法见脚本头）
- 拼接：`blueprints/Video Stitch` 或 `h3_fast_segmented.py --merge-only`（音频同步 `acrossfade d=0.3`）
- 水印：`tools/add_ai_watermark.py`
- 合规：`tools/prompt_safety_linter.py`（出片前置脱敏）

---

## 3. 路由闸门（本地版「强制顺序」）

豆包靠路由节点 Skill 卡顺序；本机用 `tools/_drama_gate.py` 做**存在性校验**来强制：

| 关卡 | 进入前必须存在 |
|---|---|
| `assets`（进资产/出图） | `00_concept/script_ep01.json` |
| `video`（进视频） | 剧本 + `01_assets/char_*_sheet.png` + `02_storyboard/storyboard.json` |
| `post`（进后期） | `03_video/*.mp4` 至少 1 个 |

```bash
python tools/_drama_gate.py --proj <proj> --date <YYYY-MM-DD> --stage video
# 退出码 0=通过, 1=未通过（可被批处理用来卡流程）
```

---

## 4. 一条龙命令骨架（先起服务，再逐段执行）

```bash
# 0) 起 ComfyUI（另开终端，常驻）
python main.py --lowvram --listen 0.0.0.0 --port 8188

# 1) 路由闸门：确认剧本就位（Counterfeit 在盘后这条才放行资产阶段）
python tools/_drama_gate.py --proj mydrama --date 2026-10-10 --stage assets

# 2) 角色资产（Counterfeit 在盘后；否则走 UI 手动出图更灵活）
python tools/_pc_gen_sd15.py Counterfeit-V3.0_fp16.safetensors 01_assets/char_aria --scenes s01,s02

# 3) 分镜关键帧（Z-Image Turbo 最快；先 --dry 校验）
python tools/_pc_gen_zimage.py --scenes s01,s02 --wh 1024x1024 \
    --outdir output/2026-10-10/mydrama/02_storyboard --dry

# 4) 视频（H3，只提交不轮询；长镜用 segmented）
python tools/h3_fast_submit.py --prompt-file p.txt \
    --first-frame output/2026-10-10/mydrama/02_storyboard/shot_001.png \
    --width 736 --height 1088 --length 124 --seed 20260906

# 5) 闸门 + 后期（字幕/配音/水印见 §2 Step5）
python tools/_drama_gate.py --proj mydrama --date 2026-10-10 --stage post
```

---

## 5. 数据结构 schema

**`script_ep01.json`**
```json
{
  "title": "剧集名",
  "episodes": [
    {"no": 1, "location": "地点", "characters": ["角色A","角色B"],
     "event": "事件", "emotion": "情绪",
     "shots": [{"id":"s01","desc":"","camera":"","motion":""}]}
  ]
}
```

**`char_ref.json`**
```json
{"name":"角色A","seed":12345,"model":"Counterfeit-V3.0_fp16",
 "lora":null,"traits":{"hair":"","clothes":"","prop":""},"sheet_path":"01_assets/char_A_sheet.png"}
```

**`storyboard.json`**
```json
[{"shot_id":"shot_001","scene":"scene_01","characters":["角色A"],
  "camera_move":"缓慢推近","char_motion":"转头微笑","env_change":"",
  "prompt":"","ref_char":"char_A_sheet.png","ref_scene":"scene_01.png",
  "first_frame":"02_storyboard/shot_001.png","duration_s":5}]
```

---

## 6. 成本 / 一致性 / 坑 速查

- **抽卡控制**：分镜先出静帧定稿再进视频（视频最贵，省 H3 积分）
- **一致性 > 单张惊艳**：锁 seed + 参考图，比反复抽卡划算
- **视频只提交不轮询**（省积分规则）；长任务结束立即取消定时
- **单实例运行**，别并行抢显存
- **⚠️ 本地代理劫持**：`HTTP_PROXY` 会让 `127.0.0.1:8188` 返回 502；所有本地 HTTP 绕代理（`urllib.request.ProxyHandler({})`）
- **H3 漏 SigmaShift → 全黑伪成功**；**Wan2.2 Animate length=49 出 53 帧 → 裁前 4 帧**；**BiRefNet 分块 32 帧**
- **`_checkv.py` 硬编码旧目录**，勿直接套用；**IPAdapter_plus 禁用** → 一致性走 种子锁 + 参考图 + ReActor + H3 首帧

---

## 7. 下一步建议
1. 先下 `Counterfeit-V3.0_fp16` 补动漫底模（方案 A）：`python tools/_dl_weights.py --set counterfeit`，下完放进 `models/checkpoints/`
2. 用一份小剧本跑通全流程最小闭环（1 角色 1 场景 1 镜），验证 H3 首帧 + 验帧
3. 跑通后再扩展到多角色多镜、加配音/字幕/配乐

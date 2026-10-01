# ComfyUI H3 视频生成 · 会话总结与后续工作

**会话时间**：2026-09-07 ~ 2026-09-08
**工作目录**：`D:\ai_projects\ComfyUI`
**核心模型**：MiniMax H3（本机 ComfyUI，16GB 显存，lowvram），`ref2va` 人脸锚定 + 文生视频，竖屏 9:16 = 544×960 @ 24fps，`steps=34, cfg=1.0, euler/simple`，`shift_video=14.0 / shift_audio=3.5`。
**参考脸**（系列同一张脸，所有题材首帧锚定）：`D:\ai_projects\ComfyUI\input\gemini_ken1\C02_PADDED.png`

---

## 一、核心方法论 / 约定（后续务必沿用）

1. **分段省显存**：H3 单段越长，峰值显存越高易爆。采用 **链式分段（3~5 段 × 72~124 帧）**，每段首帧 = 上段末帧（`-sseof -0.3` 抽帧），最后 `ffmpeg concat -c copy` 合成整体。某段失败可断点续跑（脚本会跳过已存在 mp4）。
2. **生成脚本统一入口**：放在 `tools/h3_*.py`。节点链固定为：USETLoader→CLIPLoader(minimax)→VAELoader→MiniMaxH3SigmaShift→MiniMaxH3ImageToVideo→KSampler→VAEDecode→VHS_VideoCombine。首帧经 `LoadImage`→`first_frame` 注入。
3. **两个风格系**：
   - 写实系 STYLE：`realistic cinematic photography, ultra high detail, ... glossy healthy skin`；NEG 反 `anime/cartoon/3D render`。
   - 动漫系（fashion_10pose_anime）：STYLE 用 `2D animated cel-shaded rendering`；NEG 反 `live-action photo, photorealistic`（注意方向相反）。
4. **归档**：每个题材在 `workflows/v1/prompts/2026-09-0X_<slug>.md` 建档，含采样参数表、风格/人物/镜头前缀、分段提示词、完整中文提示词版、~50字中文精简。
5. **定时轮询约定（用户明确要求）**：长任务不频繁轮询；确需轮询则做调度任务，间隔 **第1次 5 分钟 → 第2次 10 分钟 → 第3次 5 小时**，完成即取消任务。（常规做法：直接用后台 Shell 脚本自监控结束再汇报。）
6. **重复内容识别**：相同提示词/题材不与重复生成，先提示用户（例：Outfit C 因与 qipao B 相同被跳过）。
7. **技能沉淀**：已将可复用流程固化为 skills：`h3-fashion-runway`、`h3-lowvram-submit`（本会话期间出现）。后续新题材可因地制宜新建技能。

---

## 二、本会话产生 / 生成情况一览

| 题材 | 脚本 | 输出目录 | 分段 | 成片 | 状态 | 音频 |
|---|---|---|---|---|---|---|
| 单边挑眉挑战 | `tools/`（H3分段变体） | `output/h3_eyebrow_seg/` | 5段9:16 | `eyebrow_challenge_9x16_5seg.mp4` | ✅ 完成 | 待确认 |
| 走秀A（白西装黑裙） | 挖掘库脚本 | `output/h3_runway/` | 单段 | `runway_fashion_c02_9x16_full.mp4`(1.7MB) | ✅ 完成+已混音 | ✅ 有flac混入 |
| 走秀B（红金旗袍） | 挖掘库脚本 | `output/h3_runway/` | 单段 | `qipao_full.mp4`(2.9MB) | ✅ 完成+已混音 | ✅ 有flac混入 |
| 走廊法式打卡舞 | `tools/submit_h3_corridor.py` | `output/h3_corridor/` | 单段 | `corridor_full.mp4`(1.6MB) | ✅ 完成+已混音 | ✅ 有flac混入 |
| 动漫时尚短片（10姿势） | `tools/h3_fashion_10pose_anime.py` | `output/fashion_10pose_anime/` | 5段×72帧 | `fashion_10pose_anime_9x16_5seg.mp4`(5.6MB) | ✅ 完成 | ⚠️ 无声(纯video链) |
| 艾露莎Cosplay变身+舞 | `tools/h3_erza_cosplay.py` | `output/erza_cosplay/` | 2段(72+192帧) | `erza_cosplay_9x16_2seg.mp4`(3.6MB) | ✅ 完成 | ⚠️ 无声 |
| 室内性感慢摇(Heels) | `tools/h3_indoor_heels_dance.py` | `output/indoor_heels_dance/` | 3段×124帧 | `indoor_heels_dance_9x16_3seg.mp4`(3.0MB) | ✅ 完成 | ⚠️ 无声 |
| 网球裙扭腰卡点舞 | `tools/h3_tennis_skirt_dance.py` | `output/2026-09-08/tennis_skirt_dance/` | 3段×124帧 | `tennis_skirt_dance_9x16_3seg.mp4`(4.5MB) | ✅ 完成 | ⚠️ 无声 |

> 注意：从本会话中后期开始，新脚本（动漫/艾露莎/室内/网球裙）采用**纯视频节点链**，输出 mp4 **不含音轨也未生成 flac**。成片目前是**无声画面**，需要后续补配乐（见待办1）。

---

## 三、归档文档（workflows/v1/prompts/）

- `2026-09-07_eyebrow_challenge.md` — 单边挑眉挑战（5段）
- `2026-09-07_corridor_dance.md` — 走廊法式打卡舞
- `2026-09-07_fashion_10pose_anime.md` — 动漫时尚短片（10姿势，动漫渲染版）
- `2026-09-07_fairy_tail_erza_cosplay.md` — 《妖精的尾巴》艾露莎Cosplay变身+舞
- `2026-09-07_indoor_heels_dance.md` — 室内性感慢摇（Heels/Urban）
- `2026-09-07_tennis_skirt_dance.md` — 网球裙扭腰卡点摇

> 另存：`2026-09-06_browse_show.md`、`2026-09-07_fashion_10pose.md` 等更早归档（走秀源）。

---

## 四、各题材提示词要点速查（后续直接复用）

- **走秀A/B**：`C02_PADDED` 模式，full-body 居中偏右三分法，平视固定机位，EDM runway music 无 vocals；A=白blazer黑slip裙高裙衩+白棚；B=红金旗袍金绣+东方暖红棚（红帘金灯笼）。
- **走廊舞**：中景固定机位，白色长袖及膝裙+白板鞋，双手握拳胸前→挥舞→转身，法式慵懒+EDM，文案「#法修散打卡点舞 #明天就要交稿了 怎么办呀」。
- **动漫10姿势（anime版）**：`2D animated cel-shaded rendering`，极简白棚+闪光+薄雾+缎面+样张纸+光泽地面，128 BPM 加速-刹停运镜，0–15s 十姿势时间轴，NEG 反写实真人。
- **艾露莎**：SEG1 棕发眼镜少女结魔法手势+闪光→变身艾露莎战斗服（红高马尾白束胸酒红短裤臂上蓝魔纹），SEG2 女团律动，K-pop「ching ching cry cry」，字幕「正宫娘娘天生丽质」「妖尾-艾露莎」。
- **室内慢摇**：深棕长卷发+黑蕾丝吊带碎花裙+黑丝+银手链，沙发+落地灯暖光，撩拨→扭腰摆臂→慢摇Fa指定格，日系EDM，日语女声「watashi ga misete ageru kiss」，标签#美女#慢摇#舞蹈#黑丝。
- **网球裙**：白Polo（黑细边）+藏蓝百褶短裙+深棕高马尾，操绳扭腰摆臀+前行，最后双手合十点头定格，户外阳光校园感，EDM说唱hook「sixteen sixteen all day」。

---

## 五、待办 / 需要注意的坑（明确遗留项）

1. **补配乐（优先级高）**：动漫/艾露莎/室内/网球裙四条成片目前**无声**。可复用走秀的 flac→mux 思路：H3 原生音频需音频解码链（本项目旧脚本有 flac 输出），或用 `batch-faceswap`/剪辑技能混入 BGM。参考现成混音命令：
   ```
   ffmpeg -y -loglevel error -i <video>.mp4 -i <audio>.flac -c:v copy -c:a aac -b:a 192k -shortest <out>_full.mp4
   ```
2. **网球裙路径变更**：脚本已被改为日期前缀输出（`output/2026-09-08/tennis_skirt_dance/`）。后续新脚本建议统一沿用 `PREFIX = YYYY-MM-DD/<slug>` 约定，避免输出目录混乱。
3. **音频架构不统一**：旧脚本（9-06 走秀/走廊）输出视频+flac 分离；新脚本（9-07后）纯视频。若要统一，新脚本应补上 H3 音频解码节点或保留 flac。
4. 若需 H3 成片后期增强（VFI/AI超分/补帧到60fps）可用 skill `comfyui-h3-enhance`。

---

*本文档由会话自动梳理生成，供后续查看与继续工作。*
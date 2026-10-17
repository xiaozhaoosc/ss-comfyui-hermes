# MiniMax H3 动作迁移与服饰保真全链路交接文档

> **项目环境**：Windows 11 | RTX 4060 Ti (16GB VRAM) | Intel i7-14700F | ComfyUI 0.39.1  
> **归档日期**：2026-10-13  
> **交接状态**：已完成首阶段全链路跑片交付与根因排查，准备切换新会话/工具。

---

## 一、 任务背景与核心目标

1. **目标形象（Target Subject）**：
   * 输入资产：[`input/jia_ref.jpg`](file:///d:/ai_projects/ComfyUI/input/jia_ref.jpg)（Jia 全身立绘，性感粉黑蕾丝情趣吊带内衣套装）。
   * 关键特征：精致东亚面孔、长卷发、露腹马甲线、**粉黑刺绣 Bra + 低腰内裤 + 垂直黑色吊袜带细带 + 大腿黑色蕾丝环（4 件套）**。
   * 本机安全规则：本机部署的 MiniMax H3 与 Qwen3-VL **已彻底解除安全审查先验**，允许直接渲染原版内衣造型。
2. **动作与音频源（Motion & Audio Source）**：
   * 视频资产：[`input/runcha_dance.mp4`](file:///d:/ai_projects/ComfyUI/input/runcha_dance.mp4)（原视频来自 Hitomi 女仆宅舞，277 帧 @ 24fps，时长 11.54 秒）。
   * 编舞结构：
     * **0~4 秒**：双手叉腰（Hands on hips），配合节拍左右晃胯弹跳；
     * **4~7 秒**：双手小臂在胸腹前方水平交叠，随节拍轻快摇摆并歪头微笑；
     * **7~11.5 秒**：双臂自然下垂至髋旁律动弹跳，嘴型随伴奏歌词开合对口型歌唱。
3. **交付诉求**：
   * 100% 还原动作编舞与微表情（笑容、口型）；
   * 100% 保持 Jia 原图 4 件套服饰，不出现外衣腰带或牛仔裤；
   * 100% 全量时长交付（277 帧完整生成，合流原版伴奏音轨）。

---

## 二、 核心技术排查与根因剖析（避坑指南）

### 1. 白模提取是否使用 GPU？为什么表情会像“戴了面具”？
* **GPU 状态**：在 ComfyUI 中运行的 `MoGeInference`（`moge_3_vitl_fp16`）与 `BiRefNet-general` **全程驻留于 CUDA GPU**，277 帧深度法线计算耗时约 2 分钟。
* **表情丢失的根因**：
  1. **算法架构局限**：MoGe 属于*单目 3D 几何空间估计*，擅长计算躯干进深与宏观朝向，并非面部 68 点稠密特征追踪器。眼皮、眼角笑纹、嘴唇开合在 3D 毫米级深度上只有极微弱起伏，被平滑拟合算法当做高频噪声滤平；
  2. **漫反射灰阶光照陷阱**：在生成白模时，法线点乘光源计算 Lambertian 漫反射。由于人脸整体法线朝向正前，算出的灰度完全均一，失去了瞳孔、眼睑与唇缝的反差，直接呈现为平整的“白色石膏假面”；
  3. **0.5 倍降采样致命硬伤**：早期脚本粗暴加入了 `ImageScaleBy(0.5)`，导致 360P 下眼睛只有 3 个像素、嘴唇只有 2 个像素高，所有微表情与手指关节像素级损毁；
  4. **原版 v6 的真相**：作者 Aiden 原版工作流中附带的 `白模1.mp4` 实际是 3D 软件预先绑骨渲染的人形木偶（拔枪动作），并非实拍视频提取。

### 2. 服装为什么会改变？吊袜带和大腿黑色蕾丝环丢失的根因？
* **非安全审查原因**：本机模型已完全去除审查机制；
* **词义误伤根因**：原图自带“垂直吊袜带细带（straps）”与“大腿黑色蕾丝腿环（thigh bands）”。此前 Prompt 中为了消除腰封写了 `"without adding extra belts, straps"`，大模型机械化执行负面词，主动将原图的吊袜带和蕾丝环抹除；
* **解决方案**：彻底删除含 `straps` 的歧义词，在提示词中显式定义 4 件套设计，并将 `ref_image_size` 设为 `"max"`（2048px 短边高清特征注入）。

### 3. 如何实现动作与表情的高保真复刻？
* **多模态音频流接入**：将 `VHS_LoadVideo` 输出的原生音频流接入 `MiniMaxH3ReferenceToVideo` 的 `ref_video_audios` 与 `audio_vae`，利用音乐鼓点重音与人声波形强力锚定节拍跳跃，并驱动面部对口型唱歌；
* **时序编舞显式注入**：在提示词中将 11.5 秒分解为三段式精确招式注入，双重锁定手部与面部动态。

---

## 三、 已交付产物与关键文件清单

### 1. 成品视频与验收帧
| 资产类型 | 存放路径 | 规格说明 |
| :--- | :--- | :--- |
| **终极音画合流母带** | [`output/2026-10-13/v6_ultimate/jia_ultimate_dance_master.mp4`](file:///d:/ai_projects/ComfyUI/output/2026-10-13/v6_ultimate/jia_ultimate_dance_master.mp4) | 544×960, 277 帧 (11.54s), 24fps, H.264 CRF 16, 伴奏同步 |
| **0~4s 叉腰验收帧** | [`output/2026-10-13/v6_ultimate/verification_frames/sec_01_hip_hands_f30.jpg`](file:///d:/ai_projects/ComfyUI/output/2026-10-13/v6_ultimate/verification_frames/sec_01_hip_hands_f30.jpg) | 双手叉腰摇摆，吊袜带与大腿蕾丝腿环清晰在位 |
| **4~7s 叠手验收帧** | [`output/2026-10-13/v6_ultimate/verification_frames/sec_05_arms_fold_f120.jpg`](file:///d:/ai_projects/ComfyUI/output/2026-10-13/v6_ultimate/verification_frames/sec_05_arms_fold_f120.jpg) | 双手小臂水平交叠胸腹前，歪头元气甜笑 |
| **7~11s 歌唱验收帧** | [`output/2026-10-13/v6_ultimate/verification_frames/sec_09_sing_bounce_f210.jpg`](file:///d:/ai_projects/ComfyUI/output/2026-10-13/v6_ultimate/verification_frames/sec_09_sing_bounce_f210.jpg) | 双手下垂随律动弹跳，嘴型随歌词对口型开合 |
| **尾声高潮验收帧** | [`output/2026-10-13/v6_ultimate/verification_frames/sec_11_climax_f260.jpg`](file:///d:/ai_projects/ComfyUI/output/2026-10-13/v6_ultimate/verification_frames/sec_11_climax_f260.jpg) | 情绪高潮绽放灿烂笑容，服饰配件完整一致 |

### 2. 核心执行脚本与工程代码
* [`tools/run_ultimate_motion_transfer.py`](file:///d:/ai_projects/ComfyUI/tools/run_ultimate_motion_transfer.py)：
  * 完整集成音频多模态流、2048px 超清参考注入、BlockSparseAttention 稀疏加速；
  * 内建 Kitchen Attention 自愈降级与 ffmpeg 音画无损合流；
  * 全量 277 帧渲染耗时仅 **4 分 40 秒**。

### 3. 参考文档与评估资产
* [`workflows/v6/v6工作流运行评估与资源清单.md`](file:///d:/ai_projects/ComfyUI/workflows/v6/v6%E5%B7%A5%E4%BD%9C%E6%B5%81%E8%BF%90%E8%A1%8C%E8%AF%84%E4%BC%B0%E4%B8%8E%E8%B5%84%E6%BA%90%E6%B8%85%E5%8D%95.md)：包含 Aiden 原版 71 节点评估、16G 显存适配裁剪清单。
* [`workflows/v6/1-Aiden-动作迁移升级版本！法线参考！！.json`](file:///d:/ai_projects/ComfyUI/workflows/v6/1-Aiden-%E5%8A%A8%E4%BD%9C%E8%BF%81%E7%A7%BB%E5%8D%87%E7%BA%A7%E7%89%88%E6%9C%AC%EF%BC%81%E6%B3%95%E7%BA%BF%E5%8F%82%E8%80%83%EF%BC%81%EF%BC%81.json)：原版工作流。

---

## 四、 后续切换会话 / 工具推进指引

在新会话启动后，可直接选择以下两条演进路线：

### 路线 A：基于现有成片的高清母带精修（快速通道，约 2~3 分钟）
若对当前 [`jia_ultimate_dance_master.mp4`](file:///d:/ai_projects/ComfyUI/output/2026-10-13/v6_ultimate/jia_ultimate_dance_master.mp4) 的动作和表情满意，只需进一步提升画质：
1. 直接使用本地已有模型 `models/upscale_models/RealESRGAN_x4plus.pth`；
2. 运行超分脚本对 277 帧做 2x 帧级增强，输出 `1088 × 1920` 4K 级别高清视频；
3. 命令入口：`tools/enhance_h3_video.py`。

### 路线 B：打造终极“面部保留 + 身体雕塑素体”白模（白模极客通道，约 12~15 分钟）
若依然需要一份纯净的中间态“白模”：
1. **千万不要用纯法线转灰阶**（避免再次造成面部石膏化）；
2. **正确方案（Expressive Clay）**：
   * 原生 1:1 分辨率提取（杜绝 0.5 降采样）；
   * 身体区域应用 MoGe 3D 深度与环境着色，剥离女仆装，生成纯白雕塑素体；
   * 面部区域提取高对比度动态微表情（保留眼神、微笑眼弯与牙齿开合）贴合在白模头部；
   * 手部区域应用 Sobel 边缘增强，硬化叉腰与交叠手臂轮廓。

---

## 五、 服务运行与环境备忘

1. **服务启动命令**：
   ```cmd
   cmd /c d:\ai_projects\ComfyUI\venv\Scripts\python.exe -u main.py --lowvram --listen 0.0.0.0 --port 8188 --enable-assets
   ```
2. **显存释放调用**：
   在任何长时间推理前后，向 `http://127.0.0.1:8188/free` 发送 `{"unload_models": true, "free_memory": true}` 即可瞬间释放全部模型缓存至 15.8GB 纯净状态。

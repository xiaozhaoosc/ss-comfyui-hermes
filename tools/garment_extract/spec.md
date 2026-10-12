# Spec: 视频服装提取工作流（garment_extract）

## 目标
从视频目录（如 `output/2026-10-11/instagram_ayano_fj/`）提取"纯净的服装"——
去掉人物/背景，只保留服装本身的透明底 PNG（附白底版），用于参考图 / 试穿 / 训练用途。

## 最终方案（v5，经多轮抽检验证）
每帧单次推理（ComfyUI API 或本地直连）：
1. **Stage 1 关键帧抽取**（ffmpeg，CPU）：4fps 采样 → 拉普拉斯方差清晰度打分 → 去重取 Top-12
2. **Stage 2 ATR 人体解析**：`FaceProtectMask` / parsing_atr.onnx，
   clothing_labels=4,5,6,7,8（上装/裙/裤/连衣裙/腰带），排除头发(2)/墨镜(3)/脸(11)
3. **Stage 3 SAM2 边缘精修**：ATR 掩码作 soft mask input 喂 `Sam2Segmentation`
   （sam2_hiera_base_plus, fp16 + autocast）；精修面积偏离 ATR 0.5~1.6 倍时回退 ATR+羽化
4. **Stage 4 掩码清洗（scipy）**：
   - 剔除触及画面左右边缘的组件（镜面反射/其他画面碎片）
   - 剔除整体悬于主服装上方的组件（飘发误判）
   - 组件 ≥10% 主组件则保留（多件套）；第二大组件 < 主组件 40% 时只留主服装
   - 闭运算 + 填洞修复手部遮挡孔洞；bbox+8% 边距裁剪
   - 按 清晰度×√面积 排序（atr_only 回退帧 ×0.6 降权）取 Top-3

> 演进记录：v1 BiRefNet+SAM2 锚点方案被抽检否决（SAM2 分出整个人、BiRefNet 漏检透视装），
> v2 起改用 ATR 人体解析直出服装掩码。

## 使用
```powershell
# 推荐: 本地直连推理(不依赖 ComfyUI 服务器, 用 venv 运行)
D:\ai_projects\ComfyUI\venv\Scripts\python.exe tools\garment_extract\local_garment.py <视频目录>

# 备选: 走 ComfyUI API(服务器需在运行)
python tools\garment_extract\extract_garment.py <视频目录> --top 3 --frames 12
```
文件：
- `workflow_pass2.json` — ComfyUI API 工作流（LoadImage → FaceProtectMask → SAM2 → Save）
- `extract_garment.py` — API 驱动脚本
- `local_garment.py` — 本地推理脚本（onnxruntime ATR[CPU] + torch SAM2[CUDA]，免服务器）

## 输出结构
`output/<日期>/garment_extract/<视频名>/`
- `keyframes/` 候选关键帧
- `masks_raw/` ATR/SAM2 原始掩码（调试）
- `garment/garment_<n>_transparent.png` + `garment_<n>_white.png`
- `manifest.json` 来源视频/帧号/清晰度/掩码面积/方法

## 验收结果（2026-10-11 实测，4 个视频 48/48 帧成功）
- [x] 每视频 ≥3 张纯净服装图（透明底 + 白底）
- [x] 抽检：无脸部/头发/手臂/背景碎片残留；多件套完整保留
- [x] manifest.json 来源可追溯
- [x] 脚本可复用于任意视频目录

## 已知局限
- 深V/挂脖款胸口皮肤区被 protect 规则挖空（合理：服装本不覆盖皮肤）
- 头发大面积遮挡服装时边缘可能被误删（protect_labels 含 hair=2）
- ATR 对极宽松/超长外套偶尔分类不准

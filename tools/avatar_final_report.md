# Avatar 管线最终验证报告 (2026-08-15)

> 需求: 换头 + 换脸 + 换衣 + 动作迁移四合一工作流 (4 个子工作流 + 1 个合并版, MiniMax H3 收尾)

## 一、总体结论

| 工作流 | 功能 | 验证结果 | 耗时 |
|---|---|---|---|
| [avatar_wf1_head_swap.json](../workflows/avatar_wf1_head_swap.json) | 换头 (ReActor + MaskHelper SAM 蒙版) | **PASS** | ~10s |
| [avatar_wf2_face_swap.json](../workflows/avatar_wf2_face_swap.json) | 换脸 (ReActor + GFPGAN/FaceBoost) | **PASS** | <10s |
| [avatar_wf3_cloth_swap.json](../workflows/avatar_wf3_cloth_swap.json) | 换衣 (IDM-VTON 15步加速) | **PASS** | 14m56s |
| [avatar_wf4_motion_transfer.json](../workflows/avatar_wf4_motion_transfer.json) | 动作迁移 (MimicMotion 16帧) | **PASS** | ~3.5m |
| [avatar_wf5_full_pipeline.json](../workflows/avatar_wf5_full_pipeline.json) | 四合一完整版 (768×1344, 124帧, 20步) | 结构验证通过, 未执行 | 预计 >10h* |
| [avatar_wf5_short.json](../workflows/avatar_wf5_short.json) | 四合一短版 (39帧, 6步) | **前段 PASS, H3 段连通性 PASS** | 前段 475s; H3 采样 ~22min/步* |

\* H3 段瓶颈见第四节。短版 H3 采样完成 1/6 步后按用户指示停止 (GPU 91% 满载, 无 NaN/报错)。

## 二、产出资产清单 (全部保留)

### 工作流 (workflows/)
| 文件 | 说明 |
|---|---|
| avatar_wf1_head_swap.json | 换头: inswapper_128 + face_yolov8m/SAM 分割 + close/blur 羽化 |
| avatar_wf2_face_swap.json | 换脸: GFPGANv1.4 主修 + codeformer/Lanczos/0.75 二次增强 |
| avatar_wf3_cloth_swap.json | 换衣: DensePose + FaceProtectMask + IDM-VTON (demo 图对) |
| avatar_wf4_motion_transfer.json | 动作: ken4.png + _test_short2s.mp4, 20步/cfg2-3/ctx16/ov6 |
| avatar_wf5_full_pipeline.json | 完整版: 换衣→换脸→动作迁移→H3 R2V 带音频出片 |
| avatar_wf5_short.json | 短版冒烟: 16帧载入 + length=39 + 6步 |

### 输出 (output/)
| 文件 | 大小 | 来源 |
|---|---|---|
| avatar_wf1_head_swap_00001_.png | 5.3MB | WF1 |
| avatar_wf1_head_mask_00001_.png | 18KB | WF1 蒙版预览 |
| avatar_wf2_face_swap_00001_.png | 5.3MB | WF2 |
| avatar_wf3_cloth_swap_00001_.png | 740KB | WF3 |
| avatar_wf4_motion_transfer_00001.mp4/.png | 416KB/705KB | WF4 |
| avatar_wf5s_mimicmotion_00001/00002.mp4/.png | 536KB/746KB ×2 | WF5 前段 (两轮均成功) |

### 工具脚本 (tools/)
| 文件 | 说明 |
|---|---|
| smoke_test.py | 提交工作流 + 轮询结果: `python tools\smoke_test.py <wf.json> [timeout]` |
| validate_avatar_workflows.py | 结构验证: 引用完整性/连通性/输出节点 |
| download_avatar_models_v2.py | ModelScope 国内源下载 (~44GB) |
| stop_comfyui.py | 中断任务 + 清队列 + 停服务释放显存 |
| avatar_smoke_test_record.md | 过程记录 (本报告为最终版) |

## 三、修复记录 (按时间序)

1. **ultralytics 缺失**: MaskHelper 的 YOLO 报 `NameError: name 'YOLO' is not defined` → pip install ultralytics 8.4.120
2. **numpy 2.5.2 不兼容**: ultralytics 间接依赖 matplotlib C 扩展崩溃 → 降级 numpy==1.26.4 (阿里云源; 清华源 403)
3. **comfy-kitchen 0.2.10 过旧**: H3 量化模型需 `TensorCoreConvRotW4A4Layout` → 升级 kitchen 0.2.26 + aimdo 0.4.11
4. **WF5 JSON `_desc` 键**: validate_prompt 报 `AttributeError: 'str' object has no attribute 'get'` → 已删除
5. **Autogrow 输入格式**: `MiniMaxH3ReferenceToVideo` API 格式应为数组 `ref_images: [["20",0]]`, 非 `ref_image_1`
6. **SaveVideo 参数**: 第三参数是 `codec` 非 `quality`

## 四、H3 段性能瓶颈与优化 (2026-08-15 深夜已全部完成)

### 优化前基线
- 现象: 768×1344×39帧 采样 **22min/步** (6步约 2.2h; 完整版 124帧×20步估算 >10h)
- 根因链: (1) UNet 20GB > VRAM 16GB 每步跨 PCIe 换页; (2) pytorch cu124 导致 kitchen CUDA 后端 disabled, 反量化走 eager; (3) RTX 4060 Ti 无 nvfp4 硬件单元

### 三项优化 (全部落地)
| # | 优化 | 实施 | 验证 |
|---|---|---|---|
| 1 | 升级 pytorch cu130+ | torch 2.6.0+cu124 → **2.9.1+cu130** (阿里云 pytorch-wheels 镜像, torchvision 0.24.1 / torchaudio 2.9.1 同步) | kitchen CUDA 后端 `available:True, disabled:False`, 启动无 cu130 警告 |
| 2 | --lowvram 启动 | `main.py --lowvram --listen 0.0.0.0 --port 8188` | VRAM state LOW_VRAM; UNet 19.99GB "dynamic VRAM loading" 动态分块驻留 |
| 3 | 降分辨率/帧数 | [avatar_wf5_short_v2.json](../workflows/avatar_wf5_short_v2.json): 768×1344×39帧 → **480×832×22帧** (32 倍数约束保持; 计算量 21.8%) | 结构验证 PASS |

### 优化后结果 (WF5 v2 全链 PASS, 590.6s)
- **H3 采样: 22min/步 → 3.9s/步 (约 341 倍/步)**
- 归因: 分辨率/帧数下降贡献约 4.6×; 其余 ~74× 来自 kitchen CUDA 原生量化算子 (convrot_w4a4/int8_linear 等) + 动态 VRAM 加载
- 全链耗时: 换衣+换脸+动作迁移+H3 采样 6 步+双 VAE 解码 = **9.8 分钟**
- 输出规格 ffprobe 验证: 480×832@24fps×22帧 + **aac 立体声 32kHz (H3 原生音频)**
- 输出: `output/video/MiniMax_H3/avatar_wf5_v2_00001_.mp4` + `output/avatar_wf5v2_mimicmotion_00001.mp4`(中间结果)
- 兼容性: torch 升级后 WF2 快验 PASS (ReActor/onnxruntime 链无破坏)

### 完整版新版估算
- Token 量比 v2: (768×1344×124)/(480×832×22) ≈ 14.6×; 步数 20/6 ≈ 3.33×
- H3 段估算: 3.9s×14.6×3.33 ≈ 190s/步 → 20 步约 63min, 全链约 **70-80 分钟** (原估算 >10h)

### 启动命令 (优化后)
```powershell
C:\Users\kenzhao\anaconda3\python.exe main.py --lowvram --listen 0.0.0.0 --port 8188
```

## 五、环境快照

- ComfyUI 0.30.0, 前端 1.44.19
- **pytorch 2.9.1+cu130** (2026-08-15 深夜从 2.6.0+cu124 升级), RTX 4060 Ti 16GB / RAM 32GB
- comfy-kitchen 0.2.26 / comfy-aimdo 0.4.11 / numpy 1.26.4 / ultralytics 8.4.120
- 模型 (~44GB, ModelScope 国内源): MimicMotion 2.84GB + SVD 依赖 1.36GB + H3 四件套 39.55GB + SAM 357.7MB
- 启动: `C:\Users\kenzhao\anaconda3\python.exe main.py --lowvram --listen 0.0.0.0 --port 8188`

## 六、复现指南

```powershell
# 1. 启动 ComfyUI (--lowvram, 优化后)
C:\Users\kenzhao\anaconda3\python.exe main.py --lowvram --listen 0.0.0.0 --port 8188
# 2. 结构验证
python tools\validate_avatar_workflows.py
# 3. 逐个冒烟 (timeout 秒数可选)
python tools\smoke_test.py workflows\avatar_wf1_head_swap.json
python tools\smoke_test.py workflows\avatar_wf2_face_swap.json
python tools\smoke_test.py workflows\avatar_wf3_cloth_swap.json 900
python tools\smoke_test.py workflows\avatar_wf4_motion_transfer.json 600
python tools\smoke_test.py workflows\avatar_wf5_short_v2.json 1200   # 优化后全链约 10 分钟
# 4. 停止并释放显存
python tools\stop_comfyui.py
```

输入替换: WF1/WF2 改 LoadImage[1](目标)/[2](源脸); WF3 改 [1](人物)/[2](服装); WF4 改 [1](参考人)/[2](驱动视频); WF5 同上全部。

# Avatar 管线 WF1-WF5 冒烟测试记录 (2026-08-15)

## 测试环境
- ComfyUI 0.30.0, pytorch 2.6.0+cu124, RTX 4060 Ti 16GB / RAM 32GB
- comfy-kitchen 0.2.26 / comfy-aimdo 0.4.11 (从 0.2.10/0.4.7 升级, W4A4 布局可用)
- 启动: C:\Users\kenzhao\anaconda3\python.exe main.py --highvram --listen 0.0.0.0 --port 8188

## 测试结果

| 工作流 | 结果 | 耗时 | 输出 |
|---|---|---|---|
| WF1 换头 avatar_wf1_head_swap.json | PASS | ~10s | output/avatar_wf1_head_swap_00001_.png + head_mask 预览 |
| WF2 换脸 avatar_wf2_face_swap.json | PASS | <10s | output/avatar_wf2_face_swap_00001_.png |
| WF3 换衣 avatar_wf3_cloth_swap.json | PASS | 14m56s (15步) | output/avatar_wf3_cloth_swap_00001_.png |
| WF4 动作迁移 avatar_wf4_motion_transfer.json | PASS | ~3.5m (16帧) | output/avatar_wf4_motion_transfer_00001.mp4 |
| WF5 短版 avatar_wf5_short.json | 连通性 PASS / 未跑完 | 前段 475s + H3 采样 ~22min/步 | video/MiniMax_H3/avatar_wf5_short (6步×39帧预计~2h) |

## WF5 分段验证
1. IDM-VTON 换衣(15步) + ReActor 换脸 + MimicMotion(16帧): 475s 全部通过
2. Qwen3VL 文本编码器: 14.96GB full load OK
3. H3 UNet int8: 19.99GB full load OK, 混合精度 convrot_w4a4/int8_tensorwise native
4. 采样: 1/6 步完成 (22m11s/步), GPU 91% 满载, 无 NaN/报错

## 修复记录
1. ultralytics 缺失 → pip install (MaskHelper 的 YOLO 依赖)
2. numpy 2.5.2 与 matplotlib C 扩展不兼容 → 降级 numpy==1.26.4 (阿里云源; 清华源 403)
3. WF5 JSON 含 "_desc" 键导致 validate_prompt AttributeError → 已删除
4. MiniMaxH3ReferenceToVideo 的 Autogrow 输入在 API 格式下应为数组:
   "ref_images": [["20",0]], "ref_videos": [["26",0]] (非 ref_image_1/ref_video_1)
5. SaveVideo 第三参数是 codec 非 quality

## 已知限制
- H3 采样 ~22min/步: UNet 20GB > VRAM 16GB, 每步跨 PCIe 换页权重。
  优化方向: (a) 升级 pytorch cu130+ 启用 kitchen CUDA 后端 (当前 eager dequantize);
  (b) 使用 --lowvram 让模型常驻策略更合理; (c) 减小分辨率/帧数
- CUDA 后端 disabled: "You need pytorch with cu130 or higher to use optimized CUDA operations"
- comfy_kitchen CUDA backend 需 cu130, 当前 cu124 回落 eager (能跑但慢)
- 前端版本 1.44.19 < 推荐 1.47.11 (不影响 API 运行)

## 复现命令
```
python tools\smoke_test.py workflows\avatar_wf1_head_swap.json
python tools\smoke_test.py workflows\avatar_wf2_face_swap.json
python tools\smoke_test.py workflows\avatar_wf3_cloth_swap.json 900
python tools\smoke_test.py workflows\avatar_wf4_motion_transfer.json 600
python tools\smoke_test.py workflows\avatar_wf5_short.json 3600
```

## 保留资产 (勿删, 用户要求结束后再决定)
- workflows/avatar_wf1~wf5*.json (5 个工作流)
- tools/smoke_test.py, tools/validate_avatar_workflows.py
- tools/download_avatar_models_v2.py (ModelScope 源)
- output/avatar_wf* 全部输出

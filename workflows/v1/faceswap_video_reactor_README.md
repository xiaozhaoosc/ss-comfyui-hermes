# ReActor 视频换脸工作流

## 概述
基于 VHS (Video Helper Suite) + ReActor 的视频逐帧换脸工作流，自动保留原始音频。

## 流程
```
VHS_LoadVideoPath ─┬→ ReActorFaceSwap(+GFPGAN) → VHS_VideoCombine
                   └→ audio ──────────────────→ (合并音频)
LoadImage(源脸) ──┘
```

## 节点说明
| 节点 | 功能 | 关键参数 |
|------|------|---------|
| VHS_LoadVideoPath | 加载视频文件 | video=路径, frame_load_cap=0(全部) |
| LoadImage | 加载换脸源 | 文件名 |
| ReActorFaceSwap | 逐帧换脸+GFPGAN | inswapper_128.onnx |
| VHS_VideoCombine | 合成输出视频+音频 | frame_rate=30, format=h264-mp4 |

## 使用方法
1. 安装 VHS: `cd custom_nodes && git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git`
2. Load → 选择 `faceswap_video_reactor.json`
3. VHS_LoadVideoPath 输入视频路径（绝对路径）
4. LoadImage 选择换脸源
5. frame_rate 保持和源视频一致（通常25或30）
6. Queue Prompt → 输出到 `output/faceswap_video/`

## 依赖
- ComfyUI-VideoHelperSuite (VHS)
- ComfyUI-ReActor
- models/insightface/inswapper_128.onnx
- models/facerestore_models/GFPGANv1.4.pth

## 注意事项
- 大视频建议先用 frame_load_cap 测试几帧
- frame_rate 必须与源视频匹配，否则音画不同步
- 每帧处理约 0.5-2 秒（取决于 GPU）

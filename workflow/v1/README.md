D:\ai_projects\ComfyUI\workflows\v1\
├── README.md                      ← 使用说明 + 参数文档
├── outfit_swap_sam_test.json      ← 图片换装（前端导入格式）
└── video_outfit_controlnet.json   ← 视频换装（API Prompt 格式）

图片换装 — 直接在 ComfyUI 前端 Load 导入，改图片/提示词/遮罩点即可
视频换装 — API 格式，用 POST /prompt 调用或 batch_outfit_swap.py 脚本批量处理
README.md — 包含节点流程、关键参数、提示词、依赖模型、使用方式
两个工作流都经过实际验证可运行。
# 视频号 AI 形象原创证明 — 完整材料包

## 📦 材料清单

### 已准备好的文件

| # | 文件 | 说明 | 状态 |
|---|------|------|------|
| 1 | `workflows/v1/standard_zimage_realskin.json` | 人像生成工作流 JSON | ✅ |
| 2 | `workflows/idm_vton_final_workflow.json` | 换装工作流 JSON | ✅ |
| 3 | `AI形象原创证明材料.md` | 完整提示词+参数文档 | ✅ |
| 4 | ComfyUI 界面截图 | 证明使用 ComfyUI 工具 | ✅ 已截取 |

### 需要你手动截取的截图

在 ComfyUI 中依次加载以下工作流并截图：

**截图 1：人像生成工作流**
1. 打开 ComfyUI: http://127.0.0.1:8188
2. 菜单 → 工作流 → 打开 → 选择 `workflows/v1/standard_zimage_realskin.json`
3. 截取完整节点图（确保显示所有节点和连线）
4. 重点截取：提示词节点、模型加载节点、KSampler 参数

**截图 2：IDM-VTON 换装工作流**
1. 菜单 → 工作流 → 打开 → 选择 `workflows/idm_vton_final_workflow.json`
2. 截取完整节点图
3. 重点截取：IDM-VTON 节点参数、FaceProtectMask 设置

**截图 3：生成参数特写**
- KSampler 节点：steps=15, cfg=1, sampler=euler_ancestral
- Flux Guidance 节点：guidance=2.5
- LoRA 节点：两个 LoRA 的 strength 值
- IDM-VTON 节点：768×1024, 30步, guidance_scale=2.0

---

## 📝 提示词（可直接复制）

### 人像生成 — 正向提示词
```
photorealistic high-end editorial portrait, natural skin texture with visible pores and fine details, soft studio lighting, sharp focus
```
> 此提示词会与 QwenVL 自动从参考图提取的描述拼接

### 人像生成 — 反向提示词
```
（使用 ConditioningZeroOut 节点，将负面条件置零）
```

### 换装 — 服装描述
```
a black knit cardigan with white striped trim
```

### 换装 — 反向提示词
```
monochrome, lowres, bad anatomy, worst quality, low quality, artifacts, distortion
```

---

## 🔧 使用的模型清单

| 模型文件 | 用途 |
|----------|------|
| `z_image_turbo_bf16.safetensors` | Z-Image Turbo 主模型（UNet） |
| `qwen_3_4b.safetensors` | Qwen3 4B 文本编码器（CLIP） |
| `ae.safetensors` | VAE 解码器 |
| `unfiltered_realism_v2.safetensors` | 真实感增强 LoRA (0.25/0.6) |
| `kook_zimage_realistic_fantasy_turbo.safetensors` | 幻想风格 LoRA (0.1/0.4) |
| `Qwen3-VL-8B-Instruct-FP8` | 视觉理解模型（提取参考图描述） |
| IDM-VTON Pipeline (float16) | 虚拟换装模型 |

---

## 🎬 录屏建议

录制一段 2-3 分钟的操作视频，展示：

1. **打开 ComfyUI**（0:00-0:10）
   - 展示 ComfyUI 启动界面，确认工具名称
   
2. **加载人像生成工作流**（0:10-0:30）
   - 菜单 → 工作流 → 打开 → 选择 realskin.json
   - 展示完整节点图
   
3. **查看提示词和参数**（0:30-1:00）
   - 点击提示词节点，展示提示词内容
   - 点击 KSampler，展示采样参数
   - 点击 LoRA 节点，展示 LoRA 配置
   
4. **加载换装工作流**（1:00-1:30）
   - 切换到 idm_vton_final_workflow.json
   - 展示 IDM-VTON 节点和参数
   
5. **执行生成**（1:30-2:00）
   - 点击"运行"按钮
   - 展示生成进度
   - 展示最终输出结果

---

## 📋 申诉理由模板

```
本人使用 ComfyUI 开源 AI 图像生成平台，通过以下流程原创生成视频中的人物形象：

1. 使用 Z-Image Turbo 模型 + Qwen3 文本编码器生成基础人像
2. 通过 QwenVL 视觉模型自动分析参考图，提取人物描述
3. 手动编写风格提示词："photorealistic high-end editorial portrait..."
4. 使用 Realism LoRA 和 Fantasy LoRA 增强细节
5. 通过 IDM-VTON 模型实现虚拟换装

附件包含：
- ComfyUI 工作流完整截图（展示所有节点和参数）
- 完整的正向/反向提示词
- 模型配置和生成参数
- 生成过程录屏

以上材料完整展示了从模型加载、提示词输入到最终图像输出的全过程，
证明该 AI 形像是本人通过 ComfyUI 工具原创设计和制作的。
```

---

*文件位置：D:\ai_projects\ComfyUI\*
*文档位置：D:\obsidian\obsidian\ComfyUI\AI形象原创证明材料.md*

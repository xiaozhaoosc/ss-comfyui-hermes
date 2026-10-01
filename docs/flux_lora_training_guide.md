# FLUX.1 LoRA 本机微调 (炼丹) 全流程权威指南
**专为 RTX 4060 Ti (16GB 显存) 定制**

---

## 零、 训练完成后可以在本机使用吗？
**完全可以，而且非常简单！**
训练过程会产出一个以 `.safetensors` 为后缀的 LoRA 权重文件（体积通常在 100MB 到 300MB 之间）。
您只需要将这个文件复制到 `ComfyUI\models\loras\` 目录下。重启或刷新 ComfyUI 后，在您的工作流中添加一个 `Load LoRA` 节点，将它串联在基础大模型（如 `FLUX.1-dev-Abliterated-GGUF`）之后即可正常出图，全程无缝对接您的 16GB 显卡环境。

---

## 一、 训练环境准备 (推荐使用 AiToolkit)
对于 16GB 显存的用户，目前最稳定且对新手最友好的 FLUX 训练工具是 **Ostris 开发的 AiToolkit**，它针对低显存做了极限优化（支持 FP8 训练机制）。

1. **安装环境**：
   * 确保您的电脑已安装 Python 3.10+ 和 Git。
   * 打开命令行，克隆项目：
     ```bash
     git clone https://github.com/ostris/ai-toolkit.git
     cd ai-toolkit
     git submodule update --init --recursive
     ```
   * 创建虚拟环境并安装依赖：
     ```bash
     python -m venv venv
     .\venv\Scripts\activate
     pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
     pip install -r requirements.txt
     ```

## 二、 数据集准备与规范
请准备一个文件夹（例如 `D:\dataset\my_girl`），并在其中放入准备好的 15~30 张高清图片及对应的打标文件。

1. **图片要求**：
   * 数量：15 ~ 30 张。
   * 质量：短边不低于 1024 像素，清晰真实，包含多种光影、背景、衣着、角度（正/侧/全身/半身）。
   * 格式：`.jpg` 或 `.png`。
2. **打标规范 (Captioning)**：
   * 每张图片必须有一个同名的 `.txt` 文件（例：`01.jpg` 对应 `01.txt`）。
   * **内容格式**：使用自然语言描述。**只描述非特征元素（衣服、环境、光线、构图），绝对不描述长相**。
   * **加入触发词**：在每句话的最开头加入您自定义的触发词（罕见词组合最佳，如 `ohwx woman`）。
   * **示例**：`A photo of ohwx woman, standing in a brightly lit coffee shop, wearing a loose black sweater and blue jeans, looking out the window, soft sunlight.`

## 三、 最佳训练参数设置 (16GB 核心机密)
AiToolkit 使用 `.yaml` 配置文件来管理训练。您需要复制工具包中自带的 `config/examples/train_lora_flux_24gb.yaml`，并重命名为 `my_flux_lora.yaml`，然后针对 16GB 显卡进行**核心修改**：

```yaml
# 核心显存优化参数设置
job: extension
config:
  # 您的项目名称
  name: "my_first_flux_lora" 
  process:
    - type: 'sd_trainer'
      training_folder: "output"
      
      # 显存救星：必须开启
      performance_log_every: 1000
      device: cuda:0
      # 【关键1】使用 FP8 模型加载以节省显存
      trigger_word: "ohwx woman"
      network:
        type: "lora"
        linear: 16       # 推荐 Rank (Dim)。16 足够人物学习，设太大容易爆显存
        linear_alpha: 16 # 通常与 Rank 保持一致
        
      save:
        dtype: float16   # 最终保存格式
        save_every: 250  # 每 250 步保存一次备份
        max_step_saves_to_keep: 4
        
      datasets:
        - folder_path: "D:/dataset/my_girl" # 数据集绝对路径
          caption_ext: "txt"
          caption_dropout_rate: 0.05
          shuffle_tokens: false
          cache_latents_to_disk: true
          resolution: [1024, 1024]
          
      train:
        batch_size: 1    # 【关键2】16G 显卡必须设为 1
        steps: 1500      # 15~30 张图，推荐跑 1500 ~ 2000 步
        gradient_accumulation_steps: 1
        train_unet: true
        train_text_encoder: false # 绝对不要练文本编码器，否则直接爆显存
        
        # 优化器设置
        optimizer: "adamw8bit" # 【关键3】必须使用 8bit AdamW
        lr: 4e-4         # 学习率：FLUX 通常设为 4e-4 或 1e-4
        
        # 混合精度与显存优化
        dtype: bf16
        gradient_checkpointing: true # 【关键4】必须开启，否则爆显存
```

## 四、 开始炼丹
1. 打开命令行，确保激活了虚拟环境 (`.\venv\Scripts\activate`)。
2. 运行训练指令：
   ```bash
   python run.py config/my_flux_lora.yaml
   ```
3. **观察显存**：启动时会有一个显存峰值，由于开启了 FP8 和 8bit 优化器，您的 16GB 显卡占用应该会稳定在 **12.5GB - 14GB** 之间。
4. **耐心等待**：在 RTX 4060 Ti 上，1500 步的训练大约需要 **2 到 3 个小时**。

## 五、 测试与微调
1. 训练完成后，去 `ai-toolkit\output\my_first_flux_lora` 文件夹提取您的 `.safetensors` 模型。
2. 放入 ComfyUI 后，使用您打标时的触发词（如 `ohwx woman`）进行生图。
3. **调优建议**：
   * 如果脸不像：说明训练步数不够，或者数据集不够清晰。可以将 `steps` 提高到 2000。
   * 如果变成“面瘫”或画风死板（过拟合）：说明步数太多了，提取保存的中间版本（如 1000 步或 1250 步的备份文件）进行测试，或者降低 LoRA 权重至 0.8。

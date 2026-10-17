# 🎨 提示词资产库 (Prompt Asset Library)

本项目提示词资产库汇总了高阶角色设计、体态张力阶梯、异构幻想、电影级视觉工程、Wan 2.2 视频生成、连续分镜叙事及首尾帧演变的全套生产级指令与关键词资产。

---

## 目录结构
* **[MASTER_PROMPT_ASSET_LIBRARY.md](file:///d:/ai_projects/ComfyUI/prompts/MASTER_PROMPT_ASSET_LIBRARY.md)**: 核心资产文档，包含大雷身材曲线阶梯（1~12级+二次元突破比例10阶）、腹肌力量感阶梯（1~12级）、翅膀异能阶梯、特殊类提示词库（蜂腰蜜桃臀、面料紧绷湿身、神魔异构、战损符文）、Stable Diffusion 起手式、5套文生图工程指令、Wan 2.2 文/图生视频指令、4/6镜电影分镜工程指令、首尾帧动态演变指令。
* **[body_tension_special_prompts.json](file:///d:/ai_projects/ComfyUI/prompts/body_tension_special_prompts.json)**: 结构化 JSON 资产，为自动化流水线（如 `tools/asset_dedup_generator.py`）提供程序化加载的身材张力词库与特殊美学属性池。

---

## 流水线常态化激活
已在 `tools/asset_dedup_generator.py` 中深度集成：
* **身材曲线张力（Body Tension Curves）**：常态化注入沙漏比例、丰盈圆润胸部轮廓、纤细紧致腰线、天鹅颈与直角肩。
* **特殊美学特征（Special Aesthetics）**：注入冷白瓷肌微光、锁骨深邃起伏、自然动感发丝与光影折射。
* 角色生成输出自动符合 `character-wardrobe-decoupling` 方案 B 素体规范，并适配 Google Flow 与 ComfyUI 生图管线。

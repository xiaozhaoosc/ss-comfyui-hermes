# ORIENTAL_WOMAN_CHARACTER_v2 (最终定型角色资产库)

本资产库基于 Google Character Consistency（连续多视角多图迭代工作流）与 `v4` 摄影美学，建立了高精度、可长期复用的 **360° 六视图角色视觉资产库（Character Master Bible）**。

---

## 一、六视图资产速览 (360° Turnaround Sheet)

| 编号 | 视图说明 | 资产文件 | 核心控制目标 |
| :--- | :--- | :--- | :--- |
| **C01** | 正面肖像母版 (Front Portrait) | `01_IDENTITY/C01_FACE_FRONT.png` | **锁脸**：五官骨相、眼型、鼻唇结构、眼神光、发际线 |
| **C02** | 正面全身母版 (Full Body Front) | `02_BODY/C02_BODY_FRONT.png` | **锁身材**：全身头身比、沙漏形体型、基准服装剪裁与鞋子 |
| **C03** | 左侧 3/4 视图 (Left 3/4 View) | `03_ANGLES/C03_LEFT_3Q.png` | **锁左侧**：左侧面部透视、鼻梁高度、下颌线、左侧身型 |
| **C04** | 右侧 3/4 视图 (Right 3/4 View) | `03_ANGLES/C04_RIGHT_3Q.png` | **锁右侧**：右侧面部五官、发型层次、右侧身型与服装 |
| **C05** | 纯侧面 90° 轮廓 (90° Clean Profile) | `03_ANGLES/C05_PROFILE.png` | **锁侧颜**：90度鼻唇下巴角、下颌缘、天鹅颈、胸腰臀侧曲线 |
| **C06** | 背面全身视图 (Full Body Back) | `03_ANGLES/C06_BACK.png` | **锁背面**：后脑发髻、后颈、后背曲线、后腰、裙摆后缝、鞋跟 |

---

## 二、目录结构

```text
ORIENTAL_WOMAN_CHARACTER_v2
│
├── 01_IDENTITY
│   ├── C01_FACE_FRONT.png                 # 正面肖像母版图
│   └── C01_FACE_FRONT_PROMPT.txt          # 生成/复用提示词
│
├── 02_BODY
│   ├── C02_BODY_FRONT.png                 # 正面全身母版图
│   └── C02_BODY_FRONT_PROMPT.txt          # 生成/复用提示词
│
├── 03_ANGLES
│   ├── C03_LEFT_3Q.png                    # 左侧 3/4 视角
│   ├── C03_LEFT_3Q_PROMPT.txt
│   ├── C04_RIGHT_3Q.png                   # 右侧 3/4 视角
│   ├── C04_RIGHT_3Q_PROMPT.txt
│   ├── C05_PROFILE.png                    # 90° 纯侧面轮廓
│   ├── C05_PROFILE_PROMPT.txt
│   ├── C06_BACK.png                       # 背面全身视图
│   └── C06_BACK_PROMPT.txt
│
├── 04_COSTUME                             # 预留：后续衍生服装库
├── 05_STYLE                               # 预留：不同艺术/摄影风格变体
│
├── 06_VIDEO
│   └── VIDEO_CHARACTER_LOCK.txt           # Veo / 视频生成专用防漂移提示词
│
├── docs
│   └── CHARACTER_IDENTITY_LOCK.md         # 角色核心身份锁（中英双语 DNA）
│
├── README.md                              # 本说明文档
└── TODO.md                                # 项目状态追踪表
```

---

## 三、生成新场景与视频的高级组合策略

在后续制作新场景或送入 Google Veo / Flow 生成视频时，**切忌将 6 张图一次性全部输入**（避免多角度拉扯模型造成形态扭曲）。推荐按照镜头景别定向喂图：

1. **面部表演 / 特写镜头 (Close-Up / Facial Focus)**:
   * 输入参考图：`C01 (正脸) + C03 (左前) + C04 (右前)`
2. **全身动作 / 走秀镜头 (Full-Body Action)**:
   * 输入参考图：`C02 (正面全身) + C03 + C04`
3. **侧身行走 / 转身回头镜头 (Walking Profile / Turnaround)**:
   * 输入参考图：`C03 (3/4侧) + C05 (纯侧面) + C02 (全身)`
4. **背影离开镜头 (Walking Away / Back Shot)**:
   * 输入参考图：`C06 (背面全身) + C05 (侧面) + C02 (正面)`

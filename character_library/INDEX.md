# 角色库清单（INDEX.md）

> 机器可读版本：`index.json`｜可视化：`index.html`｜身份矩阵：`identity_matrix.json`
> 入库工具：`python tools/char_lib_add.py --face <图> --char-id <id> --name <名> [--alt ...]`

## 角色总表

| char_id | 显示名 | 主脸文件 | 检测分 | 备选角度（cos→主脸） | 入库日期 |
|---|---|---|---|---|---|
| char_duo3_2 | Duo3_2（第三身份） | `faces/char_duo3_2/face.jpg` | 0.816 | duo3_1.jpg(0.80)、duo3_3.jpg(0.76)、duo3_4.jpg(0.84) | 2026-10-12 |
| ↳ 备注 | 2026-10-12 四脸比对中的第三身份；duo3_1/3/4 为家族候选，同身份与否以 meta 内 cos 值为准 | | | | |
| char_duo | Duo（主用身份） | `faces/char_duo/face.png` | 0.851 | left.png(0.54) | 2026-10-12 |
| ↳ 备注 | 2026-10-12 四脸比对选定为 290 条放量用脸；与 char_duo3_2 为不同身份（cos≈0.05）；left 与主脸相似度存疑见 alt 备注 | | | | |

## 身份矩阵结论（w600k_r50 两两 cos）

- **char_duo 与 char_duo3_2 是不同身份**（cos 0.03~0.20，互相几乎正交）
- **duo3 家族 4 张（duo3_2 主 + duo3_1/duo3_3/duo3_4）互相 0.69~0.84，同一身份**
- ⚠️ **left.png vs duo.png cos=0.544**，低于同身份经验阈值 0.6——早前交接文档“duo/left 同一人”的说法**存疑**（疑侧脸角度致 embedding 漂移），待人工复核

## 效果参照成品（换脸实拍）

- `output/2026-10-12/hitomi_frontal_retest/duo3_2_final/知之者不如好之者，好之者不如乐之者.mp4` — Duo3_2（第三身份）
- `output/2026-10-12/hitomi_frontal_retest/duo_final/做简简单单的自己，过平平淡淡的生活.mp4` — Duo（主用身份）

## 来源

- char_duo3_2 ← `input\ken4\face\gpt\duo3_2.jpg`
- char_duo ← `input\ken4\face\gpt\duo.png`

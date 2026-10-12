# 服装库（garment_library）

从参考图/视频里提取的**透明底服装素材库**，供后续换装（try-on / 服装替换工作流）检索取用。

## 目录结构

```
garment_library/
├── index.json          # 机器可读索引（查库入口，勿手改，由工具维护）
├── INDEX.md            # 人读清单：总表（ID/类别/主色/尺寸/面积/版本/来源）+ 缩略图墙
├── index.html          # 可视化目录：双击浏览器打开，卡片网格 + 类别筛选 + 搜索 + 一键复制路径
├── README.md           # 本文件
├── tops/               # 上装（每件一个子目录）
│   └── <garment_id>/
│       ├── transparent.png   # 透明底 RGBA（换装工作流用这个）
│       ├── white.png         # 白底 RGB（预览/展示用）
│       ├── thumb.png         # 缩略图（清单/HTML 目录用）
│       ├── meta.json         # 该件元数据（颜色/来源/尺寸/版本/提取方法）
│       └── alts/             # 备选版本（同一件的其他候选帧，rank2/3...）
├── bottoms/            # 下装（同上）
├── full/               # 连体/整套（同上）
└── sources/            # 原始参考图存档
```

## 怎么查库

- **最快**：双击 `index.html`（缩略图墙 + 按类别筛选 + 搜索 + 点按钮复制 `.../transparent.png` 路径）
- 人读清单：`INDEX.md`
- 机器查：读 `index.json`，按 `category` / `label` / `mean_hex`（主色）/ `size` 过滤

## 怎么入库

三条路径，都用 ComfyUI venv 的 python（`D:/ai_projects/ComfyUI/venv/Scripts/python.exe`）：

```bash
# 1) 单图提取 → 登记（人工框最稳）
python tools/garment_extract/extract_from_image.py <图片> <运行目录> [--boxes top=x0,y0,x1,y1]
python tools/garment_extract/library_add.py <运行目录> --source-url ... --note "..."

# 2) 既有视频提取产物批量入库（extract_garment.py 的 <视频>/garment/garment_<rank>_*.png）
#    注意 rank1/2/3 是同一件服装的不同候选帧，不是不同部位 → 每个视频目录记为 1 件
python tools/garment_extract/library_import.py output/2026-10-11/garment_extract --category full

# 3) 刷新清单与 HTML 目录（每次入库后跑一次）
python tools/garment_extract/library_build_index.py
```

## 约定

- `garment_id` 格式：`<类别>_<日期>_<序号>`，如 `top_20261012_01` / `full_20261012_03`，入库后不改
- 类别前缀：`tops`→`top`、`bottoms`→`btm`、`full`→`full`
- `meta.json` 与 `index.json` 条目一一对应；`source_image` 指向 `sources/` 里的存档副本
- mask 提取方法：`sam2_box`（SAM2 框提示精修，首选）> `atr+sam2`（视频流水线）> `atr_only` > `raw_box`（粗框兜底）
- 入库按源图内容哈希去重，重复导入同一来源会跳过
- `alts/` 里的备选版本用于主版本不合适时替换；换装优先用根目录的 `transparent.png`

## 当前库存

见 `INDEX.md` 总表。方法 `atr+sam2` 的整套素材来自抖音参考视频（ATR 全服装区域 + SAM2 精修），
其 mask 覆盖上下装连片区域，故归 `full`；如需拆成单独上下装，需重新用 `extract_from_image.py` 分框提取。

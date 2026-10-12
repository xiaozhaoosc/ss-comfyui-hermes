# 角色库（character_library）

人脸参考资产的固化库：每个角色 = 一张换脸工作流可直接引用的参考脸 + 512 维身份向量
（insightface w600k_r50）+ 备选角度 + 效果参照成品。供后续换脸/试穿/短剧等场景
**直接取用已存在的角色**，避免反复翻 `input/ken4/face/gpt/` 拼路径。

## 目录结构

```
character_library/
├── index.json            # 机器可读索引（查库入口）
├── INDEX.md              # 人读清单（总表 + 身份矩阵结论）
├── index.html            # 可视化目录：双击浏览器打开，缩略图墙
├── identity_matrix.json  # 全库两两身份余弦矩阵（判"哪些参考其实是同一人"）
├── README.md             # 本文件
└── faces/
    └── <char_id>/
        ├── face.<ext>        # 主参考脸（ReActor source_image 直接用这个，原图拷贝）
        ├── thumb.png         # 320px 方脸缩略图（浏览用）
        ├── embedding.npy     # 512 维身份向量（w600k_r50）
        ├── meta.json         # 元数据（备选角度 cos/检测分/参照成品/来源）
        └── alts/             # 备选角度（同身份多角度，各带 _emb.npy + _thumb.png）
```

## 怎么用

- **换脸工作流取脸**：直接引用 `faces/<char_id>/face.<ext>`（例：
  `character_library/faces/char_duo/face.png`），与 `input/ken4/face/gpt/duo.png` 内容一致。
- **验身份**：`python tools/char_lib_add.py --matrix` 重算全库两两 cos；
  cos≥0.6 经验同身份，≥0.4 疑似需人工确认（侧脸/大角度会掉分，属正常）。
- **查库**：人读 `INDEX.md`；机器读 `index.json`；浏览双击 `index.html`。
- **入库新角色**：
  ```powershell
  python tools/char_lib_add.py --face <参考脸图片> --char-id char_xxx --name "显示名" `
    [--alt <同身份备选角度> --alt-note "说明"]... [--ref-output <效果参照成品>]... [--note "备注"]
  ```

## 入库时自动完成的事

RetinaFace（det_10g）取最大脸（记录 bbox + 检测分）→ w600k_r50 算 512 维归一化向量 →
拷贝原图为 `face.<ext>` → 生成方脸缩略图 → 写 `meta.json` 并更新 `index.json`。
备选角度（--alt）同样算向量并记录与主脸的 cos。

## 注意

- `face.<ext>` 是**原图直拷**（未裁剪），因为 ReActor 的 source_image 需要完整人像；
  缩略图才是裁剪版，别把 thumb 当工作流输入。
- 身份向量只用于**库内比对/去重**，不代表换脸质量；选脸仍以目视对比为准
  （参考 `output/2026-10-12/hitomi_frontal_retest/_compare/` 的四脸对比拼图）。

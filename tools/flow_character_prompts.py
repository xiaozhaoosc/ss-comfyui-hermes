#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Flow 虚拟角色 · 多视图提示词模块（英文提示词，Nano Banana 图像模式）。

用途：
  给「同一张参考脸」补齐缺失的多角度 / 表情 / 景别视图，拼出完整角色资产。
  由 `tools/flow_character_assets.py` 调用，逐视图注入 Flow 生成。

纪律（务必遵守，源自项目记忆）：
  1. 每条提示词必须声明 **单人**（single person, solo）——否则模型容易生成双人/拼图；
  2. 必须声明 **与参考图同一张脸/身份**（keep the exact same face and identity）——
     路线 A 靠参考图锁脸，路线 B（纯提示词）靠这句尽量减漂移（但仍无法真正锁身份）；
  3. 必须声明 **full-bleed 单张、无网格 / 无编号 / 无拼贴 / 无文字**——
     否则 Flow 会自动加编号、边框、文字污染产物；
  4. 背景干净、正面均匀受光，保证人脸清晰、便于后续 insightface 抽检与入库。

用法：
  from flow_character_prompts import VIEWS, build_prompt
  build_prompt("front")                       # 路线 A（参考图另由上传通道提供）
  build_prompt("left45", char_hint="Asian woman, long black hair, early 20s")  # 路线 B
  # 视图键: front / left45 / right45 / profile / back / smile / half_body / full_body
"""

# 统一约束：单人 + 锁身份 + full-bleed 无网格无文字 + 干净背景正面光
CONSTRAINTS = (
    "Single person only, solo, exactly one person in the frame. "
    "Keep the exact same face and identity as the reference image: identical facial features, "
    "same face shape, same hairstyle and hair colour, same eye colour, same skin tone, same age. "
    "Full-bleed single photograph filling the entire frame edge to edge, one continuous image. "
    "No grid, no panels, no collage, no split screen, no contact sheet, no numbering, "
    "no labels, no captions, no watermark, no text of any kind. "
    "Clean plain neutral studio background, even soft frontal lighting, sharp focus, "
    "natural skin texture, photorealistic, high detail."
)

# 各视图的专属描述（英文；键与 T4 规格一致）
VIEWS = {
    "front": (
        "Head-and-shoulders portrait, subject facing the camera straight on, "
        "body and gaze directed fully at the viewer, neutral relaxed expression, eye level, centred composition."
    ),
    "left45": (
        "Head-and-shoulders three-quarter portrait, subject's head turned 45 degrees to their own left "
        "(toward the viewer's right), both eyes still visible, neutral expression."
    ),
    "right45": (
        "Head-and-shoulders three-quarter portrait, subject's head turned 45 degrees to their own right "
        "(toward the viewer's left), both eyes still visible, neutral expression."
    ),
    "profile": (
        "Clean side profile portrait, head turned 90 degrees to a full side view, only one eye visible, "
        "nose and jawline in silhouette, neutral expression, exact same identity."
    ),
    "back": (
        "Rear view of the same person, seen from behind, back of the head, hair and shoulders visible, "
        "face not shown, same hairstyle and clothing as the reference."
    ),
    "smile": (
        "Head-and-shoulders portrait facing the camera straight on, warm natural smile with the mouth slightly open, "
        "friendly expression, eyes directed at the viewer."
    ),
    "half_body": (
        "Half-body portrait from the waist up, facing the camera, relaxed arms and hands visible, "
        "simple neutral clothing, same face and identity, centred."
    ),
    "full_body": (
        "Full-body standing photograph of the same person, whole figure from head to feet visible in frame, "
        "facing the camera, simple neutral clothing, plain studio floor and background."
    ),
}


def build_prompt(view, char_hint=""):
    """组装某视图的完整英文提示词。

    view      : VIEWS 中的视图键。
    char_hint : 外貌描述（路线 B 用），如 "Asian woman, long black hair, early 20s"，可留空。
    """
    if view not in VIEWS:
        raise KeyError("未知视图 %r（可用: %s）" % (view, ", ".join(VIEWS)))
    parts = []
    if char_hint and char_hint.strip():
        parts.append(char_hint.strip().rstrip(".") + ".")
    parts.append(VIEWS[view])
    parts.append(CONSTRAINTS)
    return " ".join(parts)


if __name__ == "__main__":
    # 自检：8 个视图键齐全，且都带单人 / 锁脸 / full-bleed 无文字约束
    expected = {"front", "left45", "right45", "profile", "back", "smile", "half_body", "full_body"}
    assert set(VIEWS) == expected, "视图键不符: %s" % sorted(VIEWS)
    for k in VIEWS:
        p = build_prompt(k)
        assert "solo" in p and "same face and identity" in p, k
        assert "Full-bleed" in p and "no grid" in p.lower() and "no text" in p.lower(), k
        print("  %-10s %d words" % (k, len(p.split())))
    print("[OK] 视图提示词自检通过：%d 视图" % len(VIEWS))
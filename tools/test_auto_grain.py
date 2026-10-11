#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""auto-grain 自动触发测试（离线层，无 GPU / 无 ComfyUI）。

mock 掉 post_prompt / wait_and_verify / verify_outputs，对
qwen_v4_submit.submit_verify_loop 的重试逻辑做 6 项断言：
  ① 阶梯触发：grain 0 → 0.004 → 0.008 依次上调，体检达标即停
  ② 重试上限：始终不达标时最多上调 2 次（0.004 → 0.008），不再继续
  ③ 阶梯上限：grain 已 0.012 时不再上调，只提交一次即停
  ④ 无 grain 节点：体检不达标但不重试，提示无法 auto-grain
  ⑤ 一次达标：首轮体检通过则只提交一次，grain 不动
  ⑥ 不体检模式：verify_fn=None 时只提交一次、不调用体检

用法: python tools/test_auto_grain.py    （全部通过退出码 0）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qwen_v4_submit as qvs

sys.stdout.reconfigure(encoding="utf-8")


def make_nodes(with_grain=True, grain=0.0):
    """构造最小 nodes：一个 [inject:grain] 节点 + 一个 [inject:output] 节点。"""
    nodes = {"30": {"inputs": {"filename_prefix": "test/out"},
                    "class_type": "SaveImage",
                    "_meta": {"title": "30. 保存图像 [inject:output]"}},
             "29": {"inputs": {"image": ["28", 0]},
                    "class_type": "SourceStub"}}
    if with_grain:
        nodes["31"] = {"inputs": {"noise_aug_strength": grain},
                       "class_type": "ImageNoiseAugmentation",
                       "_meta": {"title": "31. 末级胶片颗粒回填 [inject:grain]"}}
    return nodes


class Harness:
    """记录提交次数，verify_fn 按预设脚本逐轮返回。"""

    def __init__(self, verify_script):
        self.submits = 0
        self.verify_calls = 0
        self.verify_script = list(verify_script)   # 每轮 (ok, tex)

    def post_fn(self, nodes):
        self.submits += 1
        return {"prompt_id": f"test-{self.submits}"}

    def wait_fn(self, pid, server, timeout):
        return [Path("fake/out.png")]

    def verify_fn(self, files, image):
        ok, tex = self.verify_script[min(self.verify_calls, len(self.verify_script) - 1)]
        self.verify_calls += 1
        return ok, tex


FAIL = (False, "✘")
PASS = (True, "✔")

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("✓ " if cond else "✗ ") + name + (f"  [{detail}]" if detail else ""))


# ① 阶梯触发 + 达标即停
h = Harness([FAIL, FAIL, PASS])
nodes = make_nodes(grain=0.0)
qvs.submit_verify_loop(nodes, "restore", "src.png", "http://x", 60, True,
                       post_fn=h.post_fn, wait_fn=h.wait_fn, verify_fn=h.verify_fn)
g = nodes["31"]["inputs"]["noise_aug_strength"]
check("① 阶梯 0→0.004→0.008 且达标即停",
      h.submits == 3 and abs(g - 0.008) < 1e-9,
      f"submits={h.submits} final_grain={g}")

# ② 重试上限（始终不达标）
h = Harness([FAIL])
nodes = make_nodes(grain=0.0)
qvs.submit_verify_loop(nodes, "restore", "src.png", "http://x", 60, True,
                       post_fn=h.post_fn, wait_fn=h.wait_fn, verify_fn=h.verify_fn)
g = nodes["31"]["inputs"]["noise_aug_strength"]
check("② 始终不达标时最多上调 2 次（停在 0.008）",
      h.submits == 3 and abs(g - 0.008) < 1e-9,
      f"submits={h.submits} final_grain={g}")

# ③ 阶梯上限（已 0.012）
h = Harness([FAIL])
nodes = make_nodes(grain=0.012)
qvs.submit_verify_loop(nodes, "restore", "src.png", "http://x", 60, True,
                       post_fn=h.post_fn, wait_fn=h.wait_fn, verify_fn=h.verify_fn)
g = nodes["31"]["inputs"]["noise_aug_strength"]
check("③ grain 已 0.012 时不重试",
      h.submits == 1 and abs(g - 0.012) < 1e-9,
      f"submits={h.submits} final_grain={g}")

# ④ 无 grain 节点
h = Harness([FAIL])
nodes = make_nodes(with_grain=False)
qvs.submit_verify_loop(nodes, "restore", "src.png", "http://x", 60, True,
                       post_fn=h.post_fn, wait_fn=h.wait_fn, verify_fn=h.verify_fn)
check("④ 无 [inject:grain] 时不重试不报错", h.submits == 1, f"submits={h.submits}")

# ⑤ 首轮达标
h = Harness([PASS])
nodes = make_nodes(grain=0.0)
qvs.submit_verify_loop(nodes, "restore", "src.png", "http://x", 60, True,
                       post_fn=h.post_fn, wait_fn=h.wait_fn, verify_fn=h.verify_fn)
g = nodes["31"]["inputs"]["noise_aug_strength"]
check("⑤ 首轮体检通过只提交一次", h.submits == 1 and abs(g - 0.0) < 1e-9,
      f"submits={h.submits} final_grain={g}")

# ⑥ 不体检模式
h = Harness([PASS])
nodes = make_nodes(grain=0.0)
qvs.submit_verify_loop(nodes, "restore", "src.png", "http://x", 60, False,
                       post_fn=h.post_fn, wait_fn=h.wait_fn, verify_fn=None)
check("⑥ verify_fn=None 只提交一次不体检", h.submits == 1 and h.verify_calls == 0,
      f"submits={h.submits} verify_calls={h.verify_calls}")

n_ok = sum(1 for _, ok, _ in results if ok)
print(f"\n离线断言: {n_ok}/{len(results)} 通过")
sys.exit(0 if n_ok == len(results) else 1)

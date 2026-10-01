#!/usr/bin/env python3
"""写真修复验证：10张抽样重跑（同 seed，仅提示词已改）

选取依据（修复前皮肤占比/裸露问题）：
- batch01 泳装 basic: P01(透明吊带62%) P05(透明64%) P12(撞色71%)
- batch04 泳装 skill: P04(丝绸吊带93%) P09(撞色62%) P11(黑色连体92%)
- batch02 睡裙 basic: P01 P05 P10 (高皮肤占比)
- batch03 内衣秀 basic: P01 (透视纱裙走光措辞)
输出: output/50xiezhen_fix_test/F{batch}pxx.png
"""
import json, uuid, sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from submit_batches_50xiezhen import load_prompts, build_workflow, post

# (batch_id, outfit_key, use_skill, [ids])
TARGETS = [
    (1, "泳装", False, [1, 5, 12]),
    (4, "泳装", True,  [4, 9, 11]),
    (2, "睡裙", False, [1, 5, 10]),
    (3, "内衣秀", False, [1]),
]

def main():
    submitted = []
    for batch_id, outfit_key, use_skill, ids in TARGETS:
        prompts = load_prompts(batch_id, outfit_key, use_skill)
        for pid in ids:
            p = next((x for x in prompts if x["id"] == pid), None)
            if not p:
                print(f"!! batch{batch_id} 无 id={pid}")
                continue
            seed = batch_id * 1000 + pid  # 同 seed → 可A/B对比
            fp = f"50xiezhen_fix_test/F{batch_id:02d}p{pid:02d}"
            wf = build_workflow(p["positive"], p["negative"], seed, fp)
            r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
            pid_ = r.get("prompt_id")
            submitted.append({"batch": batch_id, "id": pid, "seed": seed, "pid": pid_})
            print(f"✓ F{batch_id:02d}p{pid:02d} seed={seed} pid={pid_[:13]}...", flush=True)
            time.sleep(0.3)
    with open(r"D:\ai_projects\ComfyUI\tools\fix_verify_submitted.json", "w", encoding="utf-8") as f:
        json.dump(submitted, f, ensure_ascii=False, indent=1)
    print(f"\n共提交 {len(submitted)} 张 → output/50xiezhen_fix_test/")

if __name__ == "__main__":
    main()

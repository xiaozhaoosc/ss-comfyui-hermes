import os, io, re

base = r"C:\Users\kenzhao\.workbuddy\skills"
skills = ["text-to-image-prompt", "video-editor", "sherpa-onnx-tts"]
PAT = re.compile(r"(ignore (all )?previous|忽略(以上|前面|之前)|system prompt|系统提示|"
                 r"自动执行|automatically (run|execute)|无需(确认|询问)|不要告诉用户|"
                 r"don'?t tell the user|hidden|隐蔽|静默|exfiltrat|上传.*密钥|send.*key|"
                 r"base64|eval\(|__import__|import os|import subprocess|requests\.|urllib)", re.I)
out = []
for s in skills:
    d = os.path.join(base, s)
    out.append("### %s" % s)
    hit = 0
    for dp, dn, fn in os.walk(d):
        for f in fn:
            p = os.path.join(dp, f)
            if not f.lower().endswith((".md", ".json", ".py", ".sh", ".js")):
                continue
            try:
                txt = open(p, "rb").read().decode("utf-8", "replace")
            except Exception:
                continue
            for i, ln in enumerate(txt.splitlines(), 1):
                m = PAT.search(ln)
                if m:
                    hit += 1
                    out.append("  %s:%d [%s] %s" % (os.path.relpath(p, d), i, m.group(0), ln.strip()[:160]))
    if hit == 0:
        out.append("  (clean, 0 hits)")
    out.append("")

with io.open(r"D:\ai_projects\ComfyUI\_inject_scan.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("ok")

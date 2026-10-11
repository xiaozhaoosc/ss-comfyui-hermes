import os, io, re

base = r"C:\Users\kenzhao\.workbuddy\skills"
skills = ["text-to-image-prompt", "video-editor", "sherpa-onnx-tts"]
out = []

KEY = re.compile(r"(curl|wget|bash|sh -c|eval\(|exec\(|os\.system|subprocess|popen|"
                 r"sudo|chmod|rm -rf|rm -r |shutil\.rmtree|pip install|npm install|"
                 r"npx |git\+https|index-url|http://|https://|ftp://|"
                 r"\.ssh|\.aws|\.env|credential|api[_-]?key|secret|token|password|"
                 r"\~/.config|APPDATA|USERPROFILE|/etc/passwd)", re.I)

for s in skills:
    d = os.path.join(base, s)
    out.append("#" * 70)
    out.append("## SKILL: %s   (%s)" % (s, d))
    if not os.path.isdir(d):
        out.append("  !! NOT INSTALLED")
        continue
    files = []
    for dp, dn, fn in os.walk(d):
        for f in fn:
            p = os.path.join(dp, f)
            try:
                sz = os.path.getsize(p)
            except Exception:
                sz = -1
            files.append((os.path.relpath(p, d), sz))
    out.append("  files (%d):" % len(files))
    for rel, sz in sorted(files):
        out.append("    %-60s %d B" % (rel, sz))
    out.append("")
    for rel, sz in sorted(files):
        if not rel.lower().endswith((".md", ".py", ".sh", ".js", ".ts", ".ps1", ".bat", ".json", ".yaml", ".yml")):
            continue
        p = os.path.join(d, rel)
        out.append("----- FILE: %s -----" % rel)
        try:
            raw = open(p, "rb").read()
            try:
                txt = raw.decode("utf-8")
            except Exception:
                txt = raw.decode("utf-8", "replace")
        except Exception as e:
            out.append("  READ ERR %s" % e)
            continue
        lines = txt.splitlines()
        if len(lines) > 260:
            out.append("  (truncated, total %d lines)" % len(lines))
            lines = lines[:260]
        for i, ln in enumerate(lines, 1):
            out.append("%4d| %s" % (i, ln))
        out.append("")

out.append("#" * 70)
out.append("## KEYWORD HITS")
for s in skills:
    d = os.path.join(base, s)
    if not os.path.isdir(d):
        continue
    out.append("### %s" % s)
    for dp, dn, fn in os.walk(d):
        for f in fn:
            p = os.path.join(dp, f)
            if not f.lower().endswith((".md", ".py", ".sh", ".js", ".ts", ".ps1", ".json", ".yaml", ".yml")):
                continue
            try:
                txt = open(p, "rb").read().decode("utf-8", "replace")
            except Exception:
                continue
            for i, ln in enumerate(txt.splitlines(), 1):
                m = KEY.search(ln)
                if m:
                    out.append("  %s:%d [%s] %s" % (os.path.relpath(p, d), i, m.group(0), ln.strip()[:200]))
    out.append("")

with io.open(r"D:\ai_projects\ComfyUI\_audit_dump.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("ok")

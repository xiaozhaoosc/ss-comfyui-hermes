import io, json, urllib.request, urllib.parse, os

queries = [
    "text to image prompt generator",
    "video editing ffmpeg",
    "text to speech offline",
]
out = []
for q in queries:
    url = "https://lightmake.site/api/v1/search?q=%s&limit=8" % urllib.parse.quote(q)
    out.append("=== %s ===" % q)
    out.append("url: " + url)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "python"})
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        res = data.get("results", data if isinstance(data, list) else [])
        if not res:
            out.append("  (empty)")
        for it in res:
            out.append("  slug=%s | name=%s | score=%s" % (
                it.get("slug"), it.get("name") or it.get("displayName"), it.get("score")))
            d = it.get("description_zh") or it.get("description") or ""
            out.append("      %s" % d[:180].replace("\n", " "))
            out.append("      dl=%s inst=%s star=%s home=%s" % (
                it.get("downloads"), it.get("installs"), it.get("stars"), it.get("homepage")))
    except Exception as e:
        out.append("  ERR %s: %s" % (type(e).__name__, e))
    out.append("")

with io.open(r"D:\ai_projects\ComfyUI\_skillhub_search.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("ok")

"""
Hitomi 批量换脸 — 输入视频预检 + 无音频补静音音轨。

背景：VHS_LoadVideo 对无音频流视频抽音会直接抛
"VHS failed to extract audio"（videohelpersuite/utils.py L224-248），
且换脸后处理的 -map 1:a 同样要求原片有音轨——两处失败点都由本脚本
一次性修复：给无音频视频补一条 44100Hz 立体声静音 AAC（视频流 copy 不重编码）。

用法：
  python tools/hitomi_precheck.py --input <目录或文件>            # 只扫描出报告
  python tools/hitomi_precheck.py --input <目录> --fix            # 扫描并补静音
  python tools/hitomi_precheck.py --input <目录> --fix --report r.txt

退出码：0=无遗留 NO_AUDIO；3=仍有未修复的无音频视频（放量门禁不过）。
备份：--fix 原地替换前把原文件移到 <input>/_precheck_backup/<相对路径>.bak，
回滚 = 把 .bak 改回 .mp4（.bak 后缀保证不会被 *.mp4 glob 命中）。
"""
import argparse
import json
import os
import subprocess
import sys

VIDEO_EXTS = (".mp4", ".avi", ".mov", ".mkv")
BACKUP_DIRNAME = "_precheck_backup"
TMP_PREFIX = "_precheck_tmp_"
MIN_TMP_BYTES = 10 * 1024
MAX_DUR_DIFF = 0.5


def probe(path):
    """一次 ffprobe 拿全量信息：视频编码/宽高/帧率、时长、音频编码。"""
    o = subprocess.run(
        ["ffprobe", "-v", "error",
         "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate",
         "-show_entries", "format=duration",
         "-of", "json", path],
        capture_output=True, text=True, timeout=60).stdout
    j = json.loads(o)
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in j.get("streams", []) if s.get("codec_type") == "audio"), None)
    if v is None:
        raise RuntimeError("无视频流")
    num, den = (v.get("r_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den) if float(den) else 30.0
    return {
        "vcodec": v.get("codec_name") or "?",
        "width": int(v.get("width") or 0),
        "height": int(v.get("height") or 0),
        "fps": fps,
        "acodec": (a or {}).get("codec_name"),
        "duration": float(j.get("format", {}).get("duration") or 0.0),
    }


def flags_of(info):
    """按探测结果打标记；NO_AUDIO 为阻塞级，其余为提示/警告。"""
    fl = []
    if not info["acodec"]:
        fl.append("NO_AUDIO")
    if info["vcodec"] != "h264":
        fl.append("NON_H264")
    if info["fps"] and all(abs(info["fps"] - x) > 1 for x in (24, 25, 30, 60)):
        fl.append("ODD_FPS")
    if info["duration"] and info["duration"] < 3:
        fl.append("SHORT")
    if info["duration"] > 90:
        fl.append("LONG")
    if info["height"] and info["height"] < 720:
        fl.append("LOW_RES")
    return fl


def collect_files(root):
    """递归收集视频文件；跳过 _precheck_backup 备份目录、下划线/点开头文件与 .bak。"""
    if os.path.isfile(root):
        return [root]
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if not d.startswith(("_", ".")) and d != BACKUP_DIRNAME]
        for name in filenames:
            if name.startswith(("_", ".")) or name.endswith(".bak"):
                continue
            if name.lower().endswith(VIDEO_EXTS):
                out.append(os.path.join(dirpath, name))
    return sorted(out)


def backup_path(root, src):
    rel = os.path.relpath(src, root)
    return os.path.join(root, BACKUP_DIRNAME, rel + ".bak")


def fix_one(root, src, info):
    """给无音频视频补静音 AAC；全校验通过才原地替换，否则保留原文件。"""
    tmp = os.path.join(os.path.dirname(src), TMP_PREFIX + os.path.basename(src))
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", src,
           "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
           "-map", "0:v", "-c:v", "copy",
           "-map", "1:a", "-c:a", "aac", "-shortest", tmp]
    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=600)
    if not os.path.exists(tmp) or os.path.getsize(tmp) < MIN_TMP_BYTES:
        raise RuntimeError("tmp 文件缺失或过小")
    t = probe(tmp)
    if t["acodec"] != "aac":
        raise RuntimeError("tmp 音轨不是 aac: %s" % t["acodec"])
    if abs(t["duration"] - info["duration"]) > MAX_DUR_DIFF:
        raise RuntimeError("时长偏差 %.2fs 超限" % abs(t["duration"] - info["duration"]))
    if (t["vcodec"], t["width"], t["height"]) != (info["vcodec"], info["width"], info["height"]):
        raise RuntimeError("视频流被转码或尺寸变化")
    bak = backup_path(root, src)
    os.makedirs(os.path.dirname(bak), exist_ok=True)
    os.replace(src, bak)
    os.replace(tmp, src)
    return t


def main():
    ap = argparse.ArgumentParser(description="Hitomi 换脸输入预检 + 无音频补静音")
    ap.add_argument("--input", required=True, help="视频目录（递归）或单个视频文件")
    ap.add_argument("--fix", action="store_true", help="给无音频视频补静音 AAC（缺省只报告）")
    ap.add_argument("--report", default=None, help="报告输出路径（缺省 <input>/_precheck_report.txt）")
    a = ap.parse_args()

    root = a.input if os.path.isdir(a.input) else os.path.dirname(os.path.abspath(a.input))
    report = a.report or os.path.join(root, "_precheck_report.txt")
    files = collect_files(a.input)
    print("扫描 %d 个视频（%s）" % (len(files), a.input))

    lines = []
    n_noaudio = n_fixed = n_failed = n_error = 0
    noaudio_list = []
    for i, f in enumerate(files, 1):
        rel = os.path.relpath(f, root)
        try:
            info = probe(f)
        except Exception as e:
            n_error += 1
            lines.append("%-52s [ERROR] %s" % (rel[:52], e))
            print("  [%d/%d] %-42s ERROR %s" % (i, len(files), rel[:42], e))
            continue
        fl = flags_of(info)
        note = ""
        if "NO_AUDIO" in fl:
            n_noaudio += 1
            noaudio_list.append(rel)
            if a.fix:
                try:
                    fix_one(root, f, info)
                    n_fixed += 1
                    note = "-> 已补静音 aac"
                    fl.remove("NO_AUDIO")
                except Exception as e:
                    n_failed += 1
                    note = "-> 修复失败: %s" % e
        lines.append("%-52s %dx%d %5.1ffps %6.1fs %-6s %-6s %s %s" % (
            rel[:52], info["width"], info["height"], info["fps"], info["duration"],
            info["vcodec"], info["acodec"] or "无音轨", ",".join(fl), note))
        print("  [%d/%d] %-42s %dx%d %.1ffps %.1fs %s %s" % (
            i, len(files), rel[:42], info["width"], info["height"], info["fps"],
            info["duration"], ",".join(fl), note))

    summary = [
        "==== 汇总 ====",
        "总数 %d ｜ 无音频 %d（修复成功 %d / 失败 %d / 遗留 %d）｜ probe 失败 %d" % (
            len(files), n_noaudio, n_fixed, n_failed, n_noaudio - n_fixed - n_failed, n_error),
    ]
    for key in ("NON_H264", "ODD_FPS", "SHORT", "LONG", "LOW_RES"):
        hits = [l.split("  ")[0].strip() for l in lines if key in l]
        if hits:
            summary.append("%s: %d 个" % (key, len(hits)))
    if noaudio_list:
        summary.append("无音频清单: " + "; ".join(noaudio_list))
    summary.append("")
    text = "\n".join(lines + summary)
    with open(report, "w", encoding="utf-8") as fp:
        fp.write(text)
    print("\n".join(summary))
    print("报告已写入 %s" % report)

    if n_noaudio - n_fixed - n_failed > 0 or n_failed > 0:
        print("[门禁] 仍有未修复的无音频视频，放量前必须处理（退出码 3）")
        sys.exit(3)


if __name__ == "__main__":
    main()

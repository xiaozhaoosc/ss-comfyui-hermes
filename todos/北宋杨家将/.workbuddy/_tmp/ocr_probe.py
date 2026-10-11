import asyncio, os, traceback

LOG = r"D:\BaiduNetdiskDownload\北宋杨家将\.workbuddy\_tmp\ocr_probe.txt"

def main():
    lines = []
    try:
        from winsdk.windows.media.ocr import OcrEngine
        from winsdk.windows.globalization import Language
        lines.append("winsdk OK")
        langs = OcrEngine.available_recognizer_languages
        lines.append("available languages: %d" % len(langs))
        for l in langs:
            lines.append("  - %s (%s)" % (l.language_tag, l.display_name))
        # try create from user profile languages
        eng = OcrEngine.try_create_from_user_profile_languages()
        lines.append("from_user_profile: %s" % (eng.recognizer_language.language_tag if eng else "None"))
        # try zh-Hans explicitly
        try:
            zh = Language("zh-Hans-CN")
            eng2 = OcrEngine.try_create_from_language(zh)
            lines.append("from_language zh-Hans-CN: %s" % ("OK" if eng2 else "None"))
        except Exception as e:
            lines.append("from_language err: %r" % (e,))
    except Exception:
        lines.append("FATAL\n" + traceback.format_exc())

    with open(LOG, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

main()

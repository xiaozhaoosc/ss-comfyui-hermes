import inspect, os, sys, time, traceback
OUT = r"D:\BaiduNetdiskDownload\北宋杨家将\.workbuddy\_tmp\ocr\introspect.txt"
lines = []
try:
    from rapidocr_onnxruntime import RapidOCR
    lines.append("RapidOCR.__init__ signature:")
    lines.append(str(inspect.signature(RapidOCR.__init__)))
    lines.append("")
    import rapidocr_onnxruntime as R
    lines.append("pkg file: " + R.__file__)
    lines.append("version: " + getattr(R, "__version__", "?"))
    src = inspect.getsource(RapidOCR.__init__)
    lines.append("--- init source ---")
    lines.append(src[:3000])
    # 找默认配置里与线程相关的键
    try:
        from rapidocr_onnxruntime.main import DEFAULT_CFG, OCR_DEFAULT_CFG
        keys = [k for k in (list(DEFAULT_CFG.keys()) + list(OCR_DEFAULT_CFG.keys())) if "thread" in k.lower() or "op" in k.lower()]
        lines.append("thread-related cfg keys: %r" % keys)
    except Exception as e:
        lines.append("cfg introspect err: %r" % (e,))
except Exception:
    lines.append("FATAL\n" + traceback.format_exc())
open(OUT, "w", encoding="utf-8").write("\n".join(lines))

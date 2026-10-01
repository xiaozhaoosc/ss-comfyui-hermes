# -*- coding: utf-8 -*-
import io, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_ps_out.txt")

p = subprocess.run(
    ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV"],
    capture_output=True)
log = p.stdout.decode("utf-8", "replace")
with io.open(OUT, "w", encoding="utf-8") as f:
    f.write(log)
    f.write("\n---- calib log size ----\n")
    cp = os.path.join(HERE, "_calib_log.txt")
    f.write("size=%d\n" % os.path.getsize(cp))

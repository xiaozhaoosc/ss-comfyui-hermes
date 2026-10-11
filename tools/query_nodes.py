import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import urllib.request
import json

res = json.loads(urllib.request.urlopen('http://127.0.0.1:8188/object_info').read())
dwp = res['DWPreprocessor']
print("DWPreprocessor input:", json.dumps(dwp['input'], indent=2))
print("DWPreprocessor output:", dwp['output'])
print("DWPreprocessor output_name:", dwp.get('output_name'))







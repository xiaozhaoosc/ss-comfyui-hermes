import urllib.request
import json

try:
    with urllib.request.urlopen("http://127.0.0.1:8188/object_info/WanAnimateToVideo") as res:
        info = json.loads(res.read().decode('utf-8'))
        print("WanAnimateToVideo info:")
        print(json.dumps(info['WanAnimateToVideo']['input'], indent=2))
except Exception as e:
    print("Error:", e)

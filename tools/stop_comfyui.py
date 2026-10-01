# 停止 ComfyUI: 中断当前任务 + 清空队列 + 杀进程释放显存
import json
import subprocess
import time
import urllib.request

SERVER = "http://127.0.0.1:8188"


def post(path, body=None):
    data = json.dumps(body).encode() if body is not None else b"{}"
    req = urllib.request.Request(f"{SERVER}{path}", data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        return urllib.request.urlopen(req, timeout=5).status
    except Exception as e:
        return f"err: {e}"


print("interrupt:", post("/interrupt"))
print("clear queue:", post("/queue", {"clear": True}))
time.sleep(3)
subprocess.run(["powershell", "-Command",
                "$p=(Get-NetTCPConnection -LocalPort 8188 -State Listen -ErrorAction SilentlyContinue).OwningProcess;"
                "if($p){Stop-Process -Id $p -Force; Write-Host \"ComfyUI stopped PID $p\"}else{Write-Host '8188 free'}"])

$env:HF_HOME = "D:\OLLAMA_MODELS\cache\huggingface"
$env:HUGGINGFACE_HUB_CACHE = "D:\OLLAMA_MODELS\cache\huggingface\hub"
$env:TORCH_HOME = "D:\OLLAMA_MODELS\cache\torch"
$env:TRANSFORMERS_CACHE = "D:\OLLAMA_MODELS\cache\transformers"
$env:XDG_CACHE_HOME = "D:\OLLAMA_MODELS\cache"
$env:PIP_CACHE_DIR = "D:\OLLAMA_MODELS\cache\pip"
$env:KMP_DUPLICATE_LIB_OK = "TRUE"

$comfy = Start-Process -FilePath "D:\ai_projects\ComfyUI\venv\Scripts\python.exe" `
    -ArgumentList "main.py", "--highvram", "--enable-manager", "--listen", "0.0.0.0", "--port", "8188" `
    -WorkingDirectory "D:\ai_projects\ComfyUI" `
    -PassThru -NoNewWindow

Write-Host "ComfyUI PID: $($comfy.Id)"
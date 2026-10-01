# 验证 torch CUDA 可用性
& "D:\ai_projects\ComfyUI\ideogram4_venv\Scripts\python.exe" -c "import torch; print('torch:', torch.__version__); print('cuda:', torch.cuda.is_available()); print('device:', torch.cuda.get_device_name(0))"

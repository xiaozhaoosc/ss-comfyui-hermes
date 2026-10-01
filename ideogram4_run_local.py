"""
Ideogram 4 本地加载 wrapper
Monkey-patch huggingface_hub.hf_hub_download，优先从本地目录加载模型，避免网络请求。
"""
import os
import sys
import json
from pathlib import Path

# 本地模型目录
LOCAL_MODEL_DIR = Path("D:/ai_projects/ComfyUI/models/ideogram4-nf4")
REPO_ID = "ideogram-ai/ideogram-4-nf4"

# 导入原始模块
sys.path.insert(0, str(Path("D:/ai_projects/ideogram4/src")))
sys.path.insert(0, str(Path("D:/ai_projects/ideogram4")))

import huggingface_hub
import huggingface_hub.file_download

# 保存原始函数
_original_hf_hub_download = huggingface_hub.file_download.hf_hub_download


def _local_hf_hub_download(repo_id, filename, **kwargs):
    """优先从本地目录加载，找不到才回退到网络"""
    # 只处理 ideogram-4-nf4 仓库
    if repo_id == REPO_ID or "ideogram-4" in str(repo_id):
        local_path = LOCAL_MODEL_DIR / filename
        if local_path.exists():
            print(f"[LOCAL] 使用本地文件: {filename}")
            return str(local_path)
        else:
            print(f"[LOCAL] 本地未找到: {filename}，尝试网络下载...")

    # 回退到原始函数
    return _original_hf_hub_download(repo_id=repo_id, filename=filename, **kwargs)


# Monkey-patch
huggingface_hub.file_download.hf_hub_download = _local_hf_hub_download
huggingface_hub.hf_hub_download = _local_hf_hub_download

# 同时 patch transformers 的 from_pretrained，让它也从本地读取
import transformers.utils.hub
_original_cached_file = transformers.utils.hub.cached_file


def _local_cached_file(pretrained_model_name_or_path, filename, **kwargs):
    """让 transformers 的 from_pretrained 也优先从本地读取"""
    if "ideogram-4" in str(pretrained_model_name_or_path):
        # 尝试多种本地路径组合
        for subfolder in ["", "text_encoder", "tokenizer"]:
            local_path = LOCAL_MODEL_DIR / subfolder / filename
            if local_path.exists():
                print(f"[LOCAL] transformers 使用本地文件: {subfolder}/{filename}")
                return str(local_path)

    return _original_cached_file(
        pretrained_model_name_or_path, filename, **kwargs
    )


transformers.utils.hub.cached_file = _local_cached_file

print(f"[LOCAL] Monkey-patch 完成，模型目录: {LOCAL_MODEL_DIR}")

# 运行原始 run_inference.py
if __name__ == "__main__":
    import runpy
    sys.argv = [
        "run_inference.py",
        "--prompt", "a ginger cat wearing a tiny wizard hat",
        "--output", "D:/ai_projects/ComfyUI/output/ideogram4_test.png",
        "--quantization", "nf4",
        "--magic-prompt-key", os.environ.get("IDEOGRAM_API_KEY", ""),
    ]
    runpy.run_path("D:/ai_projects/ideogram4/run_inference.py", run_name="__main__")

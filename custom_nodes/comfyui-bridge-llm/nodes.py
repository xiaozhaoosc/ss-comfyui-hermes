# Bridge LLM - OpenAI 兼容的 llama-server / 云厂商 桥接节点
# 支持:
#   - 本地 llama-server (base_url=http://127.0.0.1:8112, 免 api_key)
#   - 任意 OpenAI 兼容云厂商 (字节豆包/火山方舟, Qwen(DashScope), 智谱 等)
#
# 组合式设计 (简化多个节点复用):
#   BridgeLLMConfig  (配置节点) -> 只配置一次 base_url/api_key/model/采样/格式
#         |
#         v  输出 LLM_CONFIG 对象
#   BridgeLLMChat (调用节点) -> 每次只填 prompt/system/images, 复用同一份配置
#         |
#         v 输出 TEXT
#
# 特性:
#   - 流式: 接口层真流式 (requests stream=True + SSE 解析), 首 token 更快 (默认开启)
#   - json_format: 请求 response_format={"type":"json_object"} 强制输出合法 JSON
#   - 多模态: 可接收 ComfyUI 图像(IMAGE) 并发给多模态端点 (llama-server+mmproj / 云厂商视觉模型)
#
# 零额外依赖: 只用 venv 已自带的 requests + numpy + Pillow + 标准库

import base64
import io as _io

from comfy_api.latest import ComfyExtension, io

# 默认的可用 base_url / model 下拉选项
PRESET_BASE_URLS = [
    "http://127.0.0.1:8112",
    "https://ark.cn-beijing.volces.com/api/v3",                    # 字节豆包(火山方舟)
    "https://dashscope.aliyuncs.com/compatible-mode/v1",           # 阿里 Qwen
]
PRESET_MODELS = [
    "gemma-4-31b-jang-crack-Q3_K_M",
    "gemma-3-12b-it-heretic-v2-Q5_K_M",
    "deepseek-v3",   # 豆包 endpoint
    "qwen-plus",     # Qwen 模型
]


def _tensor_to_data_uri(img):
    """把 ComfyUI 的单张图像 (H,W,C) 转成 data URI。兼容 torch.Tensor / numpy。"""
    import numpy as np

    if hasattr(img, "detach"):  # torch.Tensor -> numpy
        img = img.detach().cpu().numpy()

    arr = np.asarray(img)
    # ComfyUI IMAGE 默认是 float 0-1; 若是 int 0-255 则直接用
    if arr.dtype == np.float32 or arr.dtype == np.float64:
        arr = (arr * 255.0).clip(0, 255).astype(np.uint8)
    else:
        arr = arr.astype(np.uint8)

    if arr.ndim == 3 and arr.shape[-1] == 3:  # (H,W,C) RGB
        pass
    elif arr.ndim == 3 and arr.shape[-1] == 1:  # 单通道 -> 复制成 RGB
        arr = np.concatenate([arr] * 3, axis=-1)
    elif arr.ndim == 2:  # (H,W) 灰度
        arr = np.stack([arr] * 3, axis=-1)
    else:
        raise ValueError(f"无法识别图像维度: {arr.shape}")

    from PIL import Image as PILImage
    pil_img = PILImage.fromarray(arr, mode="RGB")
    buffered = _io.BytesIO()
    pil_img.save(buffered, format="PNG")
    b64 = base64.b64encode(buffered.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _build_user_content(prompt: str, images):
    """构造 user 消息 content: 带图返回列表结构, 不带图返回纯字符串。"""
    if images is None:
        return prompt

    import numpy as np
    arr = _as_batch(images)
    B = arr.shape[0]
    content = [{"type": "text", "text": prompt}]
    for i in range(B):
        content.append({
            "type": "image_url",
            "image_url": {"url": _tensor_to_data_uri(arr[i])},
        })
    return content


def _as_batch(images):
    """把 images 归一成 (B, H, W, C) numpy 数组。"""
    import numpy as np
    if hasattr(images, "detach"):
        images = images.detach().cpu().numpy()
    arr = np.asarray(images)
    if arr.ndim == 3:  # 单张 (H,W,C) -> 补 batch
        arr = arr[None, ...]
    return arr


def _call_llm(
    prompt: str,
    base_url: str,
    api_key: str,
    model: str,
    system: str,
    max_tokens: int,
    temperature: float,
    do_stream: bool,
    response_format: str = "text",
    images=None,
) -> str:
    """对任意 OpenAI 兼容端点发一次 chat 请求。do_stream=True 走 SSE 流式累积。"""
    import requests

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": _build_user_content(prompt, images)})

    url = base_url.rstrip("/") + "/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": do_stream,
    }
    if response_format == "json":
        payload["response_format"] = {"type": "json_object"}

    try:
        resp = requests.post(
            url, json=payload, headers=headers,
            timeout=180,           # 大模型/云厂商首 token 可能较慢
            stream=do_stream,      # 流式模式下逐 chunk 读取
        )
        resp.raise_for_status()

        if not do_stream:
            data = resp.json()
            return data["choices"][0]["message"]["content"]

        # ---- 流式: 解析 SSE (data: {...}) ----
        parts = []
        for raw in resp.iter_lines(decode_unicode=True):
            line = (raw or "").strip()
            if not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                import json as _json
                delta = _json.loads(data)["choices"][0].get("delta", {})
                content = delta.get("content")
            except Exception:
                content = None
            if content:
                parts.append(content)
        return "".join(parts)

    except Exception as exc:
        return f"[BridgeLLM 错误] {exc}"


def _parse_bool(v):
    """把 'True'/'False'/bool 都归一成 bool。"""
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() == "true"


class BridgeLLMConfig(io.ComfyNode):
    """一次配置链接参数，输出可复用的 LLM_CONFIG 对象。"""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="BridgeLLMConfig",
            display_name="Bridge LLM Config",
            category="BridgeLLM",
            inputs=[
                io.Combo.Input(
                    "base_url", options=PRESET_BASE_URLS,
                    default="http://127.0.0.1:8112",
                    tooltip="OpenAI 兼容接口地址。默认本机 llama-server。",
                ),
                io.String.Input(
                    "api_key", default="",
                    tooltip="云厂商密钥。本地 llama-server 可留空。",
                ),
                io.Combo.Input(
                    "model", options=PRESET_MODELS,
                    default="gemma-4-31b-jang-crack-Q3_K_M",
                    tooltip="本地填 GGUF 文件路径/名；云厂商填对方模型 ID。",
                ),
                io.Int.Input("max_tokens", default=256, tooltip="生成的最大 token 数"),
                io.Float.Input("temperature", default=0.7,
                               min=0.0, max=2.0, step=0.01, tooltip="采样温度"),
                io.Combo.Input("stream", options=["True", "False"], default="True",
                               tooltip="接口层流式(SSE)，首 token 更快"),
                io.Combo.Input(
                    "response_format", options=["text", "json"], default="text",
                    tooltip="json 时请求 response_format=json_object，强制输出合法 JSON",
                ),
            ],
            outputs=[
                io.Custom("LLM_CONFIG").Output(display_name="CONFIG"),
            ],
        )

    @classmethod
    def execute(cls, base_url: str, api_key: str, model: str,
                max_tokens: int = 256, temperature: float = 0.7,
                stream: str = "True", response_format: str = "text") -> io.NodeOutput:
        cfg = {
            "base_url": base_url,
            "api_key": api_key,
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": _parse_bool(stream),
            "response_format": response_format,
        }
        return io.NodeOutput(cfg)


class BridgeLLMChat(io.ComfyNode):
    """用一份 LLM_CONFIG 配置发起对话，返回文本。可多个节点共用配置，支持多模态(传图)。"""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="BridgeLLMChat",
            display_name="Bridge LLM Chat",
            category="BridgeLLM",
            inputs=[
                io.Custom("LLM_CONFIG").Input("config",
                    tooltip="来自 Bridge LLM Config 的配置对象"),
                io.String.Input("prompt", default="Hello, who are you?",
                                multiline=True, tooltip="发给模型的问题/提示词"),
                io.Image.Input("images", tooltip="可选图像(支持批量)，发给多模态端点",
                               optional=True),
                io.String.Input("system", default="", multiline=True,
                                tooltip="可选的系统提示词", optional=True),
            ],
            outputs=[
                io.String.Output(display_name="TEXT"),
            ],
        )

    @classmethod
    def execute(cls, config: dict, prompt: str, images=None,
                system: str = "") -> io.NodeOutput:
        # config 是 BridgeLLMConfig 的 execute 返回的 dict
        if not isinstance(config, dict):
            return io.NodeOutput(f"[BridgeLLM 错误] 配置无效: {config!r}")
        try:
            text = _call_llm(
                prompt=prompt,
                base_url=config.get("base_url", "http://127.0.0.1:8112"),
                api_key=config.get("api_key", ""),
                model=config.get("model", ""),
                system=system,
                max_tokens=config.get("max_tokens", 256),
                temperature=config.get("temperature", 0.7),
                do_stream=bool(config.get("stream", True)),
                response_format=config.get("response_format", "text"),
                images=images,
            )
        except Exception as exc:
            text = f"[BridgeLLM 错误] {exc}"
        return io.NodeOutput(text)


class BridgeLLMImagePrompt(io.ComfyNode):
    """看图提取高精度生图提示词。接收图片+精确宽高，输出可直接用于生图的 prompt。"""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="BridgeLLMImagePrompt",
            display_name="Bridge LLM Image Prompt",
            category="BridgeLLM",
            inputs=[
                io.Custom("LLM_CONFIG").Input("config",
                    tooltip="来自 Bridge LLM Config 的配置对象"),
                io.Image.Input("image", tooltip="要分析的图片(单张)"),
                io.Int.Input("width", default=0, tooltip="精确宽度像素, 来自 GetImageSize"),
                io.Int.Input("height", default=0, tooltip="精确高度像素, 来自 GetImageSize"),
                io.String.Input(
                    "prompt_hint", default="",
                    multiline=True, tooltip="可选: 额外说明目标/风格, 会被并入请求",
                ),
            ],
            outputs=[
                io.String.Output(display_name="PROMPT"),
            ],
        )

    @classmethod
    def execute(cls, config: dict, image=None, width: int = 0, height: int = 0,
                prompt_hint: str = "") -> io.NodeOutput:
        if not isinstance(config, dict):
            return io.NodeOutput(f"[BridgeLLM 错误] 配置无效: {config!r}")
        # 组装"看图提取提示词"的指令
        dim_part = ""
        if width > 0 and height > 0:
            dim_part = (f" 图片精确分辨率为 {width}x{height} 像素。"
                        f"请在生成的提示词中保留/指定该分辨率(或给出推荐分辨率)。")
        extra = f" 额外要求: {prompt_hint}" if prompt_hint.strip() else ""
        prompt = (
            "你是图像分析助手。请仔细观察这张图片, 输出一段可直接用于图像生成 "
            "(如 FLUX/Stable Diffusion 文生图) 的高质量英文生图提示词(comma-separated tags), "
            "覆盖主体、场景、光线、构图、色调、细节。"
            + dim_part + extra
            + " 只输出提示词本身, 不要解释。"
        )
        try:
            text = _call_llm(
                prompt=prompt,
                base_url=config.get("base_url", "http://127.0.0.1:8112"),
                api_key=config.get("api_key", ""),
                model=config.get("model", ""),
                system="",
                max_tokens=config.get("max_tokens", 256),
                temperature=config.get("temperature", 0.7),
                do_stream=bool(config.get("stream", True)),
                response_format=config.get("response_format", "text"),
                images=_as_batch(image) if image is not None else None,
            )
        except Exception as exc:
            text = f"[BridgeLLM 错误] {exc}"
        return io.NodeOutput(text)


class BridgeExtension(ComfyExtension):
    """Bridge LLM 节点扩展。"""

    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [BridgeLLMConfig, BridgeLLMChat, BridgeLLMImagePrompt]


async def comfy_entrypoint() -> ComfyExtension:
    return BridgeExtension()
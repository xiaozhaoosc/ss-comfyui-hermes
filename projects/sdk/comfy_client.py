"""
ComfyUI Python Client SDK
通用的 HTTP/WebSocket 客户端，封装了上传、队列提交、进度追踪、
产物下载与 Title 锚定寻址等核心能力，供所有工作流驱动脚本复用。
"""
import json
import uuid
import time
import os
import logging
import urllib.request
import urllib.parse

import websocket  # websocket-client
import requests

logger = logging.getLogger("comfy_client")


class ComfyClient:
    """ComfyUI HTTP + WebSocket 客户端"""

    def __init__(self, host: str = "127.0.0.1", port: int = 8188, max_retries: int = 3):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.ws_url = f"ws://{host}:{port}/ws"
        self.client_id = str(uuid.uuid4())
        self.max_retries = max_retries

    # ─── 健康检查 ────────────────────────────────────────────
    def health_check(self) -> bool:
        """检测 ComfyUI 服务是否在线"""
        try:
            resp = requests.get(f"{self.base_url}/system_stats", timeout=5)
            if resp.status_code == 200:
                stats = resp.json()
                vram = stats.get("devices", [{}])[0].get("vram_total", 0)
                vram_gb = vram / (1024 ** 3) if vram else 0
                logger.info(f"ComfyUI 在线 | VRAM: {vram_gb:.1f} GB")
                return True
        except Exception as e:
            logger.error(f"ComfyUI 服务不可达: {e}")
        return False

    # ─── 图片上传 ────────────────────────────────────────────
    def upload_image(self, local_path: str, subfolder: str = "") -> str:
        """
        上传本地图片至 ComfyUI 的 input 目录。
        返回服务端文件名（用于填入 LoadImage 节点的 image 字段）。
        """
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"本地图片不存在: {local_path}")

        url = f"{self.base_url}/upload/image"
        data = {}
        if subfolder:
            data["subfolder"] = subfolder

        for attempt in range(1, self.max_retries + 1):
            try:
                with open(local_path, "rb") as f:
                    resp = requests.post(url, files={"image": f}, data=data, timeout=30)
                if resp.status_code == 200:
                    server_name = resp.json()["name"]
                    logger.info(f"上传成功: {os.path.basename(local_path)} -> {server_name}")
                    return server_name
                else:
                    logger.warning(f"上传失败 (尝试 {attempt}/{self.max_retries}): HTTP {resp.status_code}")
            except Exception as e:
                logger.warning(f"上传异常 (尝试 {attempt}/{self.max_retries}): {e}")
            if attempt < self.max_retries:
                time.sleep(2 ** attempt)

        raise RuntimeError(f"上传 {local_path} 失败，已重试 {self.max_retries} 次")

    # ─── Title 锚定寻址 ──────────────────────────────────────
    @staticmethod
    def find_node_by_title(workflow: dict, title: str) -> str | None:
        """
        通过 _meta.title 动态定位节点数字 ID。
        这使得即便 Web UI 中节点 ID 发生变动，脚本依然能精准寻址。
        """
        for node_id, node_data in workflow.items():
            if isinstance(node_data, dict):
                meta = node_data.get("_meta", {})
                if meta.get("title") == title:
                    return node_id
        return None

    @staticmethod
    def find_nodes_by_class(workflow: dict, class_type: str) -> list[str]:
        """通过 class_type 查找所有匹配的节点 ID"""
        results = []
        for node_id, node_data in workflow.items():
            if isinstance(node_data, dict) and node_data.get("class_type") == class_type:
                results.append(node_id)
        return results

    # ─── 队列提交 ────────────────────────────────────────────
    def queue_prompt(self, workflow: dict) -> str:
        """
        向 ComfyUI /prompt 接口提交工作流，返回 prompt_id。
        内置指数退避重试。
        """
        url = f"{self.base_url}/prompt"
        payload = {"prompt": workflow, "client_id": self.client_id}

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.post(url, json=payload, timeout=30)
                if resp.status_code == 200:
                    prompt_id = resp.json()["prompt_id"]
                    logger.info(f"任务已提交 | prompt_id: {prompt_id}")
                    return prompt_id
                else:
                    logger.warning(f"提交失败 (尝试 {attempt}): HTTP {resp.status_code} - {resp.text[:200]}")
            except Exception as e:
                logger.warning(f"提交异常 (尝试 {attempt}): {e}")
            if attempt < self.max_retries:
                time.sleep(2 ** attempt)

        raise RuntimeError(f"队列提交失败，已重试 {self.max_retries} 次")

    # ─── WebSocket 进度追踪 ──────────────────────────────────
    def track_progress(self, prompt_id: str, workflow: dict = None, timeout: int = 600) -> dict:
        """
        通过 WebSocket 实时追踪任务执行进度。
        返回值包含: {"status": "completed"|"error", "outputs": {...}}
        """
        ws = websocket.WebSocket()
        ws.settimeout(timeout)

        for attempt in range(1, self.max_retries + 1):
            try:
                ws.connect(f"{self.ws_url}?clientId={self.client_id}")
                logger.info("WebSocket 已连接")
                break
            except Exception as e:
                logger.warning(f"WS 连接失败 (尝试 {attempt}): {e}")
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                else:
                    raise RuntimeError("WebSocket 连接失败")

        current_node = None
        try:
            while True:
                out = ws.recv()
                if isinstance(out, str):
                    message = json.loads(out)
                    msg_type = message.get("type")
                    msg_data = message.get("data", {})

                    if msg_type == "executing":
                        # 过滤掉其他任务的消息
                        if msg_data.get("prompt_id") and msg_data["prompt_id"] != prompt_id:
                            continue

                        node_id = msg_data.get("node")
                        if node_id is not None:
                            node_title = node_id
                            if workflow and node_id in workflow:
                                node_info = workflow[node_id]
                                node_title = node_info.get("_meta", {}).get(
                                    "title", node_info.get("class_type", node_id)
                                )
                            if node_id != current_node:
                                logger.info(f"🚀 执行节点 [{node_id}] -> {node_title}")
                                current_node = node_id
                        else:
                            logger.info("🎉 工作流执行完毕!")
                            ws.close()
                            return {"status": "completed"}

                    elif msg_type == "progress":
                        value = msg_data.get("value", 0)
                        max_val = msg_data.get("max", 0)
                        logger.info(f"   ⏳ 采样进度: {value}/{max_val}")

                    elif msg_type == "execution_error":
                        error_msg = msg_data.get("exception_message", "未知错误")
                        logger.error(f"❌ 执行错误: {error_msg}")
                        ws.close()
                        return {"status": "error", "error": error_msg}

        except websocket.WebSocketTimeoutException:
            logger.error(f"WebSocket 超时 ({timeout}s)")
            ws.close()
            return {"status": "timeout"}

    # ─── 历史记录与产物下载 ──────────────────────────────────
    def get_history(self, prompt_id: str) -> dict:
        """获取指定任务的执行历史"""
        url = f"{self.base_url}/history/{prompt_id}"
        resp = requests.get(url, timeout=10)
        return resp.json().get(prompt_id, {})

    def download_outputs(self, prompt_id: str, save_dir: str) -> list[str]:
        """
        从执行历史中提取所有输出图片/视频并下载到本地。
        返回已下载的本地文件路径列表。
        """
        os.makedirs(save_dir, exist_ok=True)
        history = self.get_history(prompt_id)
        outputs = history.get("outputs", {})
        downloaded = []

        for node_id, node_output in outputs.items():
            # 图片输出
            for img in node_output.get("images", []):
                filename = img["filename"]
                subfolder = img.get("subfolder", "")
                file_type = img.get("type", "output")
                local_path = os.path.join(save_dir, filename)
                self._download_file(filename, subfolder, file_type, local_path)
                downloaded.append(local_path)

            # 视频输出 (VHS_VideoCombine 等)
            for vid in node_output.get("gifs", []) + node_output.get("videos", []):
                filename = vid.get("filename", vid) if isinstance(vid, dict) else vid
                subfolder = vid.get("subfolder", "") if isinstance(vid, dict) else ""
                file_type = vid.get("type", "output") if isinstance(vid, dict) else "output"
                local_path = os.path.join(save_dir, filename if isinstance(filename, str) else str(filename))
                self._download_file(filename, subfolder, file_type, local_path)
                downloaded.append(local_path)

        logger.info(f"已下载 {len(downloaded)} 个产物到 {save_dir}")
        return downloaded

    def _download_file(self, filename: str, subfolder: str, file_type: str, save_path: str):
        """从 ComfyUI /view 接口下载单个文件"""
        params = urllib.parse.urlencode({
            "filename": filename,
            "subfolder": subfolder,
            "type": file_type,
        })
        url = f"{self.base_url}/view?{params}"
        urllib.request.urlretrieve(url, save_path)
        logger.info(f"   已下载: {os.path.basename(save_path)}")

    # ─── 一键运行 ────────────────────────────────────────────
    def run_workflow(
        self,
        workflow_path: str,
        overrides: dict = None,
        save_dir: str = "output",
        timeout: int = 600,
    ) -> list[str]:
        """
        一键运行工作流：加载 JSON → 上传图片 → 应用参数覆盖 → 提交 → 追踪 → 下载。

        overrides 格式示例:
        {
            "SOURCE_FACE_LOADER": {"image": "/path/to/face.png"},  # 自动上传
            "POSITIVE_PROMPT": {"text": "a beautiful photo"},
            "SCHEDULER": {"steps": 20, "denoise": 0.35},
            "PULID_FLUX_APPLIER": {"weight": 0.85},
        }

        如果 override 值是一个存在的本地文件路径，且对应的 key 是 "image"，
        则自动调用 upload_image 上传并替换为服务端文件名。
        """
        # 1. 载入工作流
        with open(workflow_path, "r", encoding="utf-8") as f:
            workflow = json.load(f)

        # 2. 应用参数覆盖
        if overrides:
            for title, params in overrides.items():
                node_id = self.find_node_by_title(workflow, title)
                if node_id is None:
                    logger.warning(f"Title 锚定未找到: '{title}'，跳过")
                    continue
                for key, value in params.items():
                    # 自动上传图片
                    if key == "image" and isinstance(value, str) and os.path.isfile(value):
                        value = self.upload_image(value)
                    workflow[node_id]["inputs"][key] = value
                    logger.debug(f"参数覆盖: [{node_id}].{key} = {value}")

        # 3. 提交
        prompt_id = self.queue_prompt(workflow)

        # 4. 追踪进度
        result = self.track_progress(prompt_id, workflow=workflow, timeout=timeout)
        if result["status"] != "completed":
            logger.error(f"任务未成功完成: {result}")
            return []

        # 5. 下载产物
        return self.download_outputs(prompt_id, save_dir)

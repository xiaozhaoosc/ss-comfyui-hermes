import os
import sys
import io
import json
import re
import time
import datetime
import logging
import collections
import urllib.request
import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    P2ImMessageReceiveV1,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
    CreateMessageRequest,
    CreateMessageRequestBody,
)

# 0. Windows 控制台 UTF-8 与行缓冲
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

# 1. 日志格式化
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("FeishuBridge")

# 2. 飞书凭据配置
FEISHU_APP_ID = "REDACTED_APP_ID"
FEISHU_APP_SECRET = "REDACTED_SECRET"

# 3. 工作空间与持久化路径
WORKSPACE_DIR = r"d:\ai_projects\ComfyUI"
OUTPUT_DIR = os.path.join(WORKSPACE_DIR, "output")
TODOS_DIR = os.path.join(WORKSPACE_DIR, "todos")
os.makedirs(TODOS_DIR, exist_ok=True)
TODOS_FILE = os.path.join(TODOS_DIR, "feishu_tasks.json")

# 初始化 Lark OpenAPI 客户端
api_client = lark.Client.builder() \
    .app_id(FEISHU_APP_ID) \
    .app_secret(FEISHU_APP_SECRET) \
    .log_level(lark.LogLevel.INFO) \
    .build()

# 消息去重队列
PROCESSED_MSG_IDS = collections.deque(maxlen=200)

# ==================== 机舱状态与任务反射模块 ====================

def get_gpu_status() -> str:
    """获取 4060 Ti 显存与硬件状态"""
    try:
        import torch
        if torch.cuda.is_available():
            dev_name = torch.cuda.get_device_name(0)
            total = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            allocated = torch.cuda.memory_allocated(0) / (1024 ** 3)
            reserved = torch.cuda.memory_reserved(0) / (1024 ** 3)
            return f"{dev_name} | 已分配: {allocated:.2f}GB / 保留: {reserved:.2f}GB / 总计: {total:.2f}GB"
        return "未检测到 CUDA 设备"
    except Exception as e:
        return f"显卡状态检测异常: {e}"

def get_comfyui_queue_status():
    """获取 ComfyUI 实时任务队列状态"""
    try:
        url = "http://127.0.0.1:8188/queue"
        req = urllib.request.Request(url, headers={"User-Agent": "FeishuBridge"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            running = data.get("queue_running", [])
            pending = data.get("queue_pending", [])
            
            running_info = []
            for item in running:
                prompt_id = item[1]
                prompt_dict = item[2]
                
                # 提取模型与输出配置
                models = []
                steps = None
                output_prefix = None
                for node_id, node in prompt_dict.items():
                    class_type = node.get("class_type", "")
                    inputs = node.get("inputs", {})
                    if "unet_name" in inputs:
                        models.append(inputs["unet_name"])
                    elif "ckpt_name" in inputs:
                        models.append(inputs["ckpt_name"])
                    if "steps" in inputs and steps is None:
                        steps = inputs["steps"]
                    if "filename_prefix" in inputs:
                        output_prefix = inputs["filename_prefix"]
                        
                model_desc = models[0] if models else "默认模型"
                running_info.append({
                    "id": prompt_id[:8] + "...",
                    "full_id": prompt_id,
                    "model": model_desc,
                    "steps": steps,
                    "output_prefix": output_prefix
                })
                
            return {
                "online": True,
                "running": running_info,
                "pending_count": len(pending)
            }
    except Exception as ex:
        return {
            "online": False,
            "error": str(ex),
            "running": [],
            "pending_count": 0
        }

def get_recent_outputs(hours=24, limit=6):
    """扫描 output/ 目录下今天/近期生成的文件"""
    cutoff = time.time() - (hours * 3600)
    files_list = []
    if os.path.exists(OUTPUT_DIR):
        for root, _, files in os.walk(OUTPUT_DIR):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in [".png", ".jpg", ".jpeg", ".mp4", ".flac", ".wav", ".webp"]:
                    fp = os.path.join(root, f)
                    try:
                        mtime = os.path.getmtime(fp)
                        if mtime >= cutoff:
                            files_list.append({
                                "name": f,
                                "rel_path": os.path.relpath(fp, OUTPUT_DIR),
                                "size_mb": round(os.path.getsize(fp) / (1024 * 1024), 2),
                                "mtime": mtime,
                                "time_str": datetime.datetime.fromtimestamp(mtime).strftime("%H:%M:%S")
                            })
                    except OSError:
                        pass
    files_list.sort(key=lambda x: x["mtime"], reverse=True)
    return files_list[:limit], len(files_list)

def load_feishu_tasks():
    """读取飞书发布的历史任务清单"""
    if os.path.exists(TODOS_FILE):
        try:
            with open(TODOS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_feishu_task(content: str, sender_id: str) -> dict:
    """保存新发布的任务"""
    tasks = load_feishu_tasks()
    task_id = "TASK-" + datetime.datetime.now().strftime("%m%d-%H%M%S")
    new_task = {
        "id": task_id,
        "content": content,
        "sender": sender_id,
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "QUEUED"
    }
    tasks.insert(0, new_task)
    with open(TODOS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks[:100], f, ensure_ascii=False, indent=2)
    return new_task

# ==================== 智能业务响应生成 ====================

def build_workspace_and_progress_report() -> str:
    """生成工作空间与任务进展报告"""
    lines = [
        "🛸【4060 Ti 机舱 · 工作空间与任务进展看板】",
        f"📂 工作空间: {WORKSPACE_DIR}",
        f"🖥️ 物理算力: {get_gpu_status()}",
        ""
    ]
    
    # 1. ComfyUI 当前工作流与队列状态
    comfy = get_comfyui_queue_status()
    if comfy["online"]:
        if comfy["running"]:
            r = comfy["running"][0]
            lines.append("⚡【当前正在运行的工作流】:")
            lines.append(f"  • 任务 ID: {r['id']}")
            lines.append(f"  • 驱动模型: {r['model']}")
            if r['output_prefix']:
                lines.append(f"  • 目标前缀: {r['output_prefix']}")
            if r['steps']:
                lines.append(f"  • 采样步数: {r['steps']} steps")
            lines.append(f"  • 队列等待: {comfy['pending_count']} 个任务排队中")
        else:
            lines.append(f"⚡【ComfyUI 状态】: 处于空闲待命状态 (队列等待: {comfy['pending_count']})")
    else:
        lines.append("⚠️【ComfyUI 状态】: 端口 8188 离线或未响应")
        
    lines.append("")

    # 2. 今日产物与任务清单
    recent_files, total_count = get_recent_outputs(hours=24, limit=5)
    lines.append(f"📦【今日完成产物清单】(近24h共计生成 {total_count} 个文件):")
    if recent_files:
        for idx, item in enumerate(recent_files, 1):
            lines.append(f"  {idx}. [{item['time_str']}] {item['name']} ({item['size_mb']} MB)")
    else:
        lines.append("  (今天暂无新生成的图片/视频产物)")

    # 3. 飞书已发布任务队列
    feishu_tasks = load_feishu_tasks()
    if feishu_tasks:
        lines.append("")
        lines.append(f"📋【飞书任务队列 (最近 {len(feishu_tasks[:3])} 项)】:")
        for t in feishu_tasks[:3]:
            lines.append(f"  • [{t['status']}] {t['id']}: {t['content'][:25]}")

    lines.append("")
    lines.append("💡 发送【发布任务 <内容>】即可随时向机舱提交新指令。")
    return "\n".join(lines)

def build_task_list_report() -> str:
    """生成飞书已发布任务清单"""
    tasks = load_feishu_tasks()
    if not tasks:
        return "📋【机舱任务清单】\n当前暂无通过飞书发布的新任务。发送【发布任务 <内容>】即可提交！"
    
    lines = ["📋【机舱任务清单 (最新 10 条)】:"]
    for idx, t in enumerate(tasks[:10], 1):
        lines.append(f"{idx}. [{t['status']}] {t['id']} ({t['created_at'][11:16]})")
        lines.append(f"   内容: {t['content']}")
    lines.append("\n💡 发送【进展】可查看 ComfyUI 当前运行节点与产物生成进展。")
    return "\n".join(lines)

# ==================== 消息核心路由 (废除死板白名单) ====================

def route_and_execute(raw_text: str, sender_id: str) -> str:
    """智能意图路由引擎：自然语言理解，不再死板拦截"""
    text = raw_text.strip()
    lower_text = text.lower()

    # 1. 连通性测试
    if lower_text == "ping":
        return "pong! 4060 Ti 机舱通信正常 🚀"

    # 2. 帮助菜单
    if lower_text in ["帮助", "help", "?", "？"]:
        return (
            "🤖【4060 Ti 飞书中枢控制台】\n\n"
            "你可以直接发送自然语言，支持以下核心功能：\n\n"
            "1. 📊【查看进展】\n"
            "   发送：进展 / 进度 / 工作空间 / 任务清单 / 今天完成了什么\n"
            "   功能：查看 ComfyUI 正在运行的工作流、今日产物列表、GPU 显存负载\n\n"
            "2. 🚀【发布任务】\n"
            "   发送：发布任务 <内容>（例如：发布任务 批量生成5张科幻机甲）\n"
            "   功能：自动登记并加入机舱待办流水线\n\n"
            "3. 📋【任务清单】\n"
            "   发送：任务清单 / 待办 / todos\n"
            "   功能：查看已发布的历史任务与当前状态\n\n"
            "4. 🖥️【硬件状态】\n"
            "   发送：状态 / status / gpu\n"
            "   功能：实时上报 4060 Ti 16GB 显存使用情况"
        )

    # 3. 硬件状态查询
    if lower_text in ["状态", "status", "gpu", "显卡"]:
        return f"🖥️【4060 Ti 物理状态】\n• 硬件: {get_gpu_status()}\n• 工作空间: {WORKSPACE_DIR}\n• 飞书连接: 官方 WebSocket (稳定在线)"

    # 4. 任务发布意图识别 (发布任务 / 任务: / 生成 / 画 / 跑工作流)
    publish_prefix_match = re.match(r"^(发布任务|创建任务|新建任务|任务[:：]|todo[:：])\s*(.+)", text, re.IGNORECASE)
    if publish_prefix_match:
        task_content = publish_prefix_match.group(2).strip()
        new_task = save_feishu_task(task_content, sender_id)
        return (
            f"✅【任务发布成功】\n"
            f"• 任务编号: {new_task['id']}\n"
            f"• 任务内容: {new_task['content']}\n"
            f"• 当前状态: 已录入机舱待办队列 (QUEUED)\n"
            f"• 创建时间: {new_task['created_at']}\n\n"
            f"机舱任务中枢已建档，发送【进展】可跟踪 ComfyUI 算力调度进度。"
        )

    # 5. 查看进展 / 工作空间 / 今日完成产物意图识别
    progress_keywords = ["进展", "进度", "工作空间", "清单", "今天", "今日", "产物", "队列", "正在运行", "comfyui", "完成"]
    if any(k in lower_text for k in progress_keywords):
        return build_workspace_and_progress_report()

    # 6. 任务清单专用查询
    if any(k in lower_text for k in ["待办", "todos", "任务列表"]):
        return build_task_list_report()

    # 7. 开放式自然语言理解与友好交互 (不再死板拦截)
    # 若用户输入包含“生成”、“画”、“制作”、“跑一下”，自动作为任务登记建议
    if any(k in lower_text for k in ["生成", "画", "制作", "跑一下", "执行", "测试"]):
        new_task = save_feishu_task(text, sender_id)
        return (
            f"🤖 已自动为你将需求录入机舱任务队列：\n"
            f"• 任务编号: {new_task['id']}\n"
            f"• 需求内容: {text}\n"
            f"• 状态: QUEUED (已排队)\n\n"
            f"你可以随时发送【进展】查看 4060 Ti 算力运行情况，或发送【帮助】查看更多功能。"
        )

    # 兜底友好回应
    return (
        f"🤖 已收到你的消息：「{text}」\n\n"
        f"当前飞书中枢支持随时查看进展与发布任务：\n"
        f"• 发送【进展】：查看当前工作空间、正在运行的 ComfyUI 模型与今日产物\n"
        f"• 发送【发布任务 <内容>】：提交新任务至 4060 Ti 调度队列\n"
        f"• 发送【帮助】：查看完整指令集"
    )

# ==================== 飞书通信与 WebSocket ====================

def extract_text_content(msg_type: str, raw_content: str) -> str:
    """解析 text 与 post 消息"""
    if not raw_content:
        return ""
    try:
        data = json.loads(raw_content)
    except Exception:
        return raw_content.strip()

    if msg_type == "text":
        text = data.get("text", "")
    elif msg_type == "post":
        texts = []
        def traverse(node):
            if isinstance(node, dict):
                if node.get("tag") == "text":
                    texts.append(node.get("text", ""))
                elif node.get("tag") == "a":
                    texts.append(node.get("text", "") or node.get("href", ""))
                else:
                    for v in node.values():
                        traverse(v)
            elif isinstance(node, list):
                for item in node:
                    traverse(item)
        traverse(data)
        text = " ".join("".join(texts).split())
    else:
        text = str(data)

    # 去除开头的 @bot
    cleaned = re.sub(r"^@\S+\s*", "", text).strip()
    return cleaned

def reply_feishu_message(message_id: str, chat_id: str, reply_text: str):
    """向飞书回复消息"""
    try:
        reply_req = ReplyMessageRequest.builder() \
            .message_id(message_id) \
            .request_body(
                ReplyMessageRequestBody.builder()
                .msg_type("text")
                .content(json.dumps({"text": reply_text}))
                .build()
            ).build()
        resp = api_client.im.v1.message.reply(reply_req)
        if resp.success():
            logger.info(f"✅ 成功回复消息 [{message_id}]")
            return
        else:
            logger.warning(f"引用回复未成功 code={resp.code}, msg={resp.msg}，回退至会话发送...")
    except Exception as e:
        logger.warning(f"引用回复异常: {e}，回退至会话发送...")

    if chat_id:
        try:
            req = CreateMessageRequest.builder() \
                .receive_id_type("chat_id") \
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type("text")
                    .content(json.dumps({"text": reply_text}))
                    .build()
                ).build()
            resp = api_client.im.v1.message.create(req)
            if resp.success():
                logger.info(f"✅ 成功发送至会话 [{chat_id}]")
            else:
                logger.error(f"❌ 发送至会话失败 code={resp.code}, msg={resp.msg}")
        except Exception as ex:
            logger.error(f"❌ 直接发送异常: {ex}")

def on_message_received(data: P2ImMessageReceiveV1) -> None:
    event = data.event
    msg = event.message
    message_id = msg.message_id
    chat_id = msg.chat_id
    
    if message_id in PROCESSED_MSG_IDS:
        return
    PROCESSED_MSG_IDS.append(message_id)

    sender_id = event.sender.sender_id.open_id if event.sender and event.sender.sender_id else "unknown"
    text_content = extract_text_content(msg.message_type, msg.content)
    if not text_content:
        return

    logger.info(f"📥 收到指令: \"{text_content}\" (来自: {sender_id})")

    # 执行智能路由
    reply_text = route_and_execute(text_content, sender_id)
    logger.info(f"📤 响应内容:\n{reply_text}")

    # 回复飞书
    reply_feishu_message(message_id, chat_id, reply_text)

# 构建事件分发与长连接
event_handler = lark.EventDispatcherHandler.builder("", "") \
    .register_p2_im_message_receive_v1(on_message_received) \
    .build()

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 飞书智能控制中枢已启动 (ComfyUI / 4060 Ti 机舱调度)")
    logger.info(f"🔑 App ID: {FEISHU_APP_ID}")
    logger.info(f"📂 工作空间: {WORKSPACE_DIR}")
    logger.info("🛡️ 模式: 开放智能意图识别 (已废除死板白名单限制)")
    logger.info("=" * 60)
    
    client = lark.ws.Client(
        app_id=FEISHU_APP_ID,
        app_secret=FEISHU_APP_SECRET,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO
    )
    
    try:
        client.start()
    except KeyboardInterrupt:
        logger.info("服务已停止")
    except Exception as ex:
        logger.error(f"长连接服务异常: {ex}")

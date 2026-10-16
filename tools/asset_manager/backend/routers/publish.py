# -*- coding: utf-8 -*-
"""视频发布任务路由：为每个平台创建后台发布任务，状态与日志随变更落盘。"""
import json
import re
import threading
import traceback
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import ASSET_MANAGER_DIR, ROOT_DIR
from ..publishers import PUBLISHERS, UPLOAD_POST_PLATFORMS
from ..publishers import upload_post

router = APIRouter(prefix="/api/publish", tags=["Publish"])

OUTPUT_ROOT = (ROOT_DIR / "output").resolve()
PUBLISH_JOBS_DIR = ASSET_MANAGER_DIR / "publish_jobs"
PUBLISH_CONFIG_PATH = ASSET_MANAGER_DIR / "publish_config.json"
PUBLISH_MODES = {"publish", "draft", "manual"}
WECHAT_MP_MEDIA_TYPES = {"video", "images", "article"}

# job_id -> job dict，任务仅在创建时执行一次，服务重启后只恢复记录不重跑
_jobs = {}


def load_publish_config():
    """读取 publish_config.json，文件不存在时返回空配置。"""
    if not PUBLISH_CONFIG_PATH.exists():
        return {}
    return json.loads(PUBLISH_CONFIG_PATH.read_text(encoding="utf-8"))


def save_publish_config(config):
    PUBLISH_CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def _persist(job):
    PUBLISH_JOBS_DIR.mkdir(parents=True, exist_ok=True)
    path = PUBLISH_JOBS_DIR / f"{job['job_id']}.json"
    path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")


def _set_status(job, status):
    job["status"] = status
    job["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _persist(job)


def _append_log(job, message):
    stamp = datetime.now().strftime("%H:%M:%S")
    job["logs"].append(f"[{stamp}] {message}")
    job["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _persist(job)


import collections

_PLATFORM_LOCKS = collections.defaultdict(threading.Lock)


def _run_job(job_id, upload_post_key=None):
    job = _jobs[job_id]
    platform = job["platform"]

    def log(message):
        _append_log(job, message)

    try:
        _set_status(job, "running")
        lock = _PLATFORM_LOCKS[platform] if platform in PUBLISHERS else None
        if lock:
            if not lock.acquire(blocking=False):
                log(f"平台 [{platform}] 当前有任务在运行，进入排队等待...")
                lock.acquire(blocking=True)
                log(f"已获取平台 [{platform}] 执行锁，开始执行。")
        try:
            if platform in UPLOAD_POST_PLATFORMS:
                config = load_publish_config()
                api_key = upload_post_key or config.get("upload_post_api_key", "")
                user = config.get("upload_post_user", "")
                if not api_key or not user:
                    log("未配置 Upload-Post API Key 或用户名，请在发布设置中填写（publish_config.json）")
                    _set_status(job, "failed")
                    return
                result = upload_post.publish([platform], job["video_path"], job["title"], api_key, user, log)
                _set_status(job, result[platform])
            else:
                kwargs = {
                    "publish_mode": job.get("publish_mode", "publish"),
                }
                if platform in ("wechat_mp", "shipinhao"):
                    kwargs["content"] = job.get("content", "")
                if platform == "wechat_mp":
                    if job.get("media_type") != "video":
                        kwargs["media_type"] = job["media_type"]
                        kwargs["image_paths"] = job.get("image_paths", [job["video_path"]])
                status = PUBLISHERS[platform](
                    job["video_path"], job["title"], job["tags"], log, **kwargs)
                _set_status(job, status)
        finally:
            if lock and lock.locked():
                lock.release()
    except Exception as e:
        log(f"发布任务异常：{e}")
        log(f"异常堆栈：\n{traceback.format_exc()}")
        _set_status(job, "failed")


def _resolve_output_file(file_rel_path):
    target = (OUTPUT_ROOT / file_rel_path).resolve()
    if not target.is_relative_to(OUTPUT_ROOT):
        raise HTTPException(status_code=400, detail="文件路径越界，必须位于 output 目录内")
    if not target.is_file():
        raise HTTPException(status_code=400, detail=f"视频文件不存在：{file_rel_path}")
    return target


STYLE_MAPPINGS = {
    "linen": "亚麻质感",
    "backlit": "逆光美学",
    "roumei": "柔美优雅",
    "qwen": "精选视觉",
    "dress": "长裙穿搭",
    "maxi": "高雅裙装",
    "cinematic": "电影感光影",
    "hanfu": "新中式国风",
    "suit": "气质西装",
    "urban": "都市格调",
    "street": "街头日常",
    "portrait": "唯美写真",
    "motion": "动感瞬间",
    "tune": "质感精调",
    "selflift": "自律律动",
}


def _extract_prompt_text(target_path):
    if target_path.suffix.lower() == ".png":
        try:
            from PIL import Image
            with Image.open(target_path) as im:
                raw = im.info.get("prompt")
                if raw:
                    data = json.loads(raw)
                    for node in data.values():
                        inputs = node.get("inputs", {})
                        text = inputs.get("text") or inputs.get("prompt")
                        if isinstance(text, str) and len(text.strip()) > 15:
                            low = text.lower()
                            if any(neg in low for neg in ["lowres", "bad anatomy", "deformed", "watermark", "nsfw"]):
                                continue
                            return text.strip()
        except Exception:
            pass
    return ""


class PublishJobRequest(BaseModel):
    file_rel_path: str
    file_rel_paths: Optional[List[str]] = None
    platforms: List[str]
    title: str = ""
    content: Optional[str] = ""
    tags: Optional[List[str]] = None
    upload_post_key: Optional[str] = None
    publish_mode: str = "publish"  # publish=自动发布 draft=存草稿 manual=仅填表人工确认
    media_type: str = "video"      # video | images | article（后两者仅公众号）


@router.post("/jobs")
def create_publish_jobs(payload: PublishJobRequest):
    """为请求中的每个平台各创建一个发布任务，后台线程执行。"""
    file_path = _resolve_output_file(payload.file_rel_path)
    rel_paths = payload.file_rel_paths if payload.file_rel_paths else [payload.file_rel_path]
    image_paths = [str(_resolve_output_file(r)) for r in rel_paths]
    if payload.publish_mode not in PUBLISH_MODES:
        raise HTTPException(status_code=400, detail=f"不支持的发布模式：{payload.publish_mode}")
    media_type = payload.media_type if payload.media_type in WECHAT_MP_MEDIA_TYPES else "video"
    if media_type != "video" and file_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(status_code=400, detail="公众号贴图/文章模式必须选择图片资产")
    platforms = list(dict.fromkeys(payload.platforms))
    unknown = [p for p in platforms if p not in PUBLISHERS and p not in UPLOAD_POST_PLATFORMS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"不支持的平台：{'、'.join(unknown)}")
    if media_type != "video" and set(platforms) - {"wechat_mp"}:
        raise HTTPException(status_code=400, detail="贴图/文章模式目前仅支持公众号平台")
    job_title = payload.title.strip()
    job_content = (payload.content or "").strip()
    job_tags = payload.tags or []
    if not job_title or not job_content:
        try:
            suggested = suggest_metadata(payload.file_rel_path)
            if not job_title:
                job_title = suggested["title"]
            if not job_content:
                job_content = suggested["content"]
            if not job_tags:
                job_tags = suggested["tags"]
        except Exception:
            pass

    batch_id = uuid.uuid4().hex[:8]
    created = []
    for platform in platforms:
        job_id = uuid.uuid4().hex[:12]
        now = datetime.now().isoformat(timespec="seconds")
        job = {
            "job_id": job_id,
            "batch_id": batch_id,
            "platform": platform,
            "file_rel_path": payload.file_rel_path.replace("\\", "/"),
            "file_rel_paths": [r.replace("\\", "/") for r in rel_paths],
            "video_path": str(file_path),
            "image_paths": image_paths,
            "title": job_title,
            "content": job_content,
            "tags": job_tags,
            "publish_mode": payload.publish_mode,
            "media_type": media_type,
            "status": "pending",
            "logs": [],
            "created_at": now,
            "updated_at": now,
        }
        _jobs[job_id] = job
        _persist(job)
        threading.Thread(target=_run_job, args=(job_id, payload.upload_post_key), daemon=True).start()
        created.append(job)
    return {"batch_id": batch_id, "jobs": created}


def _match_character_for_asset(target_path, prompt_text=""):
    """从数据库匹配资产对应的角色中文名称与特色风格。"""
    try:
        from ..database import SessionLocal
        from ..models import CharacterModel
        db = SessionLocal()
        try:
            chars = db.query(CharacterModel).all()
            stem_lower = target_path.stem.lower()
            rel_lower = target_path.as_posix().lower()
            prompt_str = prompt_text or ""
            # 1. 优先根据 char_id 精准匹配（如 char_cen_youqing_2204_01）
            for c in chars:
                cid = c.char_id.lower()
                cid_short = cid.replace("char_", "")
                if cid in stem_lower or cid in rel_lower or cid_short in stem_lower or cid_short in rel_lower:
                    return c
            # 2. 检查角色中文名称是否包含在路径或 prompt 中
            for c in chars:
                m = re.match(r"^([\u4e00-\u9fa5]+)", c.name or "")
                if m:
                    cn = m.group(1)
                    if cn in target_path.as_posix() or cn in prompt_str:
                        return c
            # 3. 按拼音前缀组合匹配（如 cen_youqing / jiang_qinghuan）
            for c in chars:
                parts = [p for p in c.char_id.lower().split("_") if p not in ("char", "01", "02", "03")]
                if len(parts) >= 2:
                    sub = "_".join(parts[:2])
                    if sub in stem_lower or sub in rel_lower:
                        return c
        finally:
            db.close()
    except Exception:
        pass
    return None


@router.get("/suggest")
def suggest_metadata(file_rel_path: str):
    """根据文件名、Prompt元数据与目录结构生成发布标题、正文内容与话题标签建议。"""
    target = _resolve_output_file(file_rel_path)
    rel = target.relative_to(OUTPUT_ROOT).as_posix()
    parts = rel.split("/")
    prompt = _extract_prompt_text(target)

    stem = re.sub(r"[_\-]?\d{4,8}(_\d+)?$", "", target.stem)
    stem_clean = re.sub(r"^(pc|img|vid|output)[_\-]", "", stem, flags=re.I)
    stem_clean = re.sub(r"[_\-]+", " ", stem_clean).strip() or target.stem

    combined_text = f"{stem} {' '.join(parts)} {prompt}".lower()
    matched_styles = [cn for en, cn in STYLE_MAPPINGS.items() if en in combined_text]

    char = _match_character_for_asset(target, prompt)
    char_name = ""
    char_style = ""
    if char:
        m = re.match(r"^([\u4e00-\u9fa5]+)", char.name or "")
        char_name = m.group(1) if m else char.name.split()[0]
        style_match = re.search(r"[·•]\s*([^)]+)", char.name or "")
        char_style = style_match.group(1).strip() if style_match else ""

    # 1. 标题建议：全中文表达，优先使用角色名与艺术风格
    if char_name:
        style_part = char_style or (" ｜ ".join(dict.fromkeys(matched_styles[:2])) if matched_styles else "自然光影")
        title = f"{char_name} ｜ {style_part}写真集"
    elif matched_styles:
        title = " ｜ ".join(dict.fromkeys(matched_styles[:2])) + "写真集"
    else:
        title = "光影美学 ｜ AI视觉写真集"

    # 2. 标签建议
    tags = ["AI摄影", "光影美学"]
    if char_name and char_name not in tags:
        tags.append(char_name)
    if char_style and char_style not in tags:
        tags.append(char_style)
    for s in matched_styles:
        if s not in tags:
            tags.append(s)
    for p in parts[:-1]:
        if p != "output" and not re.match(r"^\d{4}-\d{2}-\d{2}", p):
            if re.search(r"[\u4e00-\u9fa5]", p) or p.upper() in ("AI", "COMFYUI", "OOTD"):
                tags.append(p)
    config = load_publish_config()
    tags = list(dict.fromkeys(config.get("default_tags", []) + tags))[:8]

    # 3. 正文内容建议
    if char_name:
        intro_subject = f"本期带来「{char_name}」的精选视觉呈现"
        if char_style:
            intro_subject += f"，诠释「{char_style}」的独特意境与东方神韵"
    else:
        style_desc = "、".join(matched_styles) if matched_styles else "自然光影与质感"
        intro_subject = f"本期带来以「{style_desc}」为主题的视觉创作，定格唯美雅致的每个细节"

    content = (
        f"✨ 【光影与视觉精选】\n"
        f"{intro_subject}。柔和的自然光漫过视线，细腻捕捉每一处动人质感与从容姿态。\n\n"
        f"📷 画面构想 / 提示词：\n"
        f"{prompt[:260] if prompt else '以细腻光影勾勒唯美画卷，展现真实质感与艺术张力。'}\n\n"
        f"✨ 艺术风格：\n"
        f"{char_style or ('、'.join(matched_styles) if matched_styles else '自然光影美学、胶片质感写真')}\n\n"
        f"定格属于光与影的唯美瞬间。"
    )

    # 4. 同目录下其他图片资产（同批次候选）
    siblings = []
    if target.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
        try:
            for p in sorted(target.parent.glob("*")):
                if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                    s_rel = p.relative_to(OUTPUT_ROOT).as_posix()
                    siblings.append({
                        "rel_path": s_rel,
                        "name": p.name,
                        "preview_url": f"/api/comfy-assets/output/file?rel_path={s_rel}"
                    })
        except Exception:
            pass

    return {
        "title": title[:30],
        "content": content,
        "tags": tags[:8],
        "title_by_platform": {
            "shipinhao": title[:16],
            "douyin": title[:30],
        },
        "siblings": siblings[:24],
    }


@router.get("/jobs")
def list_publish_jobs():
    """发布任务列表，按创建时间倒序。"""
    jobs = sorted(_jobs.values(), key=lambda j: j["created_at"], reverse=True)
    return [{k: v for k, v in job.items() if k != "logs"} for job in jobs]


@router.get("/jobs/{job_id}")
def get_publish_job(job_id: str):
    """任务详情，含日志。"""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _jobs[job_id]


class PublishConfigPayload(BaseModel):
    upload_post_api_key: Optional[str] = None
    upload_post_user: Optional[str] = None
    default_tags: Optional[List[str]] = None


@router.get("/config")
def get_publish_config():
    config = load_publish_config()
    return {
        "upload_post_api_key": config.get("upload_post_api_key", ""),
        "upload_post_user": config.get("upload_post_user", ""),
        "default_tags": config.get("default_tags", []),
    }


@router.post("/config")
def update_publish_config(payload: PublishConfigPayload):
    config = load_publish_config()
    if payload.upload_post_api_key is not None:
        config["upload_post_api_key"] = payload.upload_post_api_key
    if payload.upload_post_user is not None:
        config["upload_post_user"] = payload.upload_post_user
    if payload.default_tags is not None:
        config["default_tags"] = [t.strip() for t in payload.default_tags if t.strip()]
    save_publish_config(config)
    return {"status": "saved"}


class OpenBrowserPayload(BaseModel):
    platform: str


PLATFORM_URLS = {
    "wechat_mp": "https://mp.weixin.qq.com/",
    "shipinhao": "https://channels.weixin.qq.com/platform/post/create",
    "douyin": "https://creator.douyin.com/",
    "kuaishou": "https://cp.kuaishou.com/",
}


def _launch_interactive_browser(platform: str, url: str):
    """通过 Windows 交互会话机制在用户的真实物理桌面（WinSta0\\default）上弹出 Chrome。"""
    from ..publishers.selenium_base import (
        PROFILE_ROOT, _cleanup_stale_profile_locks, _is_port_listening,
        _launch_desktop_chrome, _start_chrome, PLATFORM_DEBUG_PORTS
    )
    profile_dir = PROFILE_ROOT / platform
    profile_dir.mkdir(parents=True, exist_ok=True)
    port = PLATFORM_DEBUG_PORTS.get(platform, 9527)

    if _is_port_listening(port):
        try:
            from selenium import webdriver
            options = webdriver.ChromeOptions()
            options.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
            d = _start_chrome(options)
            d.get(url)
        except Exception:
            pass
    else:
        _cleanup_stale_profile_locks(profile_dir)
        _launch_desktop_chrome(platform, profile_dir, port, initial_url=url)

    try:
        import ctypes
        user32 = ctypes.windll.user32
        h_desk = user32.OpenDesktopW('default', 0, False, 0x0100)
        def _bring_front(hwnd, l):
            buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, buf, 512)
            if any(k in buf.value for k in ["Chrome", "微信", "视频号", "抖音", "快手"]):
                user32.ShowWindow(hwnd, 3)
                user32.SetForegroundWindow(hwnd)
            return True
        CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
        user32.EnumDesktopWindows(h_desk, CB(_bring_front), 0)
        user32.CloseDesktop(h_desk)
    except Exception:
        pass


@router.post("/browser/open")
def open_platform_browser(payload: OpenBrowserPayload):
    platform = payload.platform
    if platform not in PLATFORM_URLS:
        raise HTTPException(status_code=400, detail=f"不支持的平台: {platform}")

    url = PLATFORM_URLS[platform]
    threading.Thread(target=_launch_interactive_browser, args=(platform, url), daemon=True).start()
    return {"status": "opened", "platform": platform}


def _load_persisted_jobs():
    """启动时从 publish_jobs/ 恢复任务记录；中断的任务标记 failed，不重复执行。"""
    if not PUBLISH_JOBS_DIR.exists():
        return
    for path in PUBLISH_JOBS_DIR.glob("*.json"):
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if "job_id" not in job:
            continue
        if job.get("status") in ("pending", "running"):
            job["status"] = "failed"
            stamp = datetime.now().strftime("%H:%M:%S")
            job["logs"].append(f"[{stamp}] 服务重启，任务中断，未继续执行")
            job["updated_at"] = datetime.now().isoformat(timespec="seconds")
            path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        _jobs[job["job_id"]] = job


_load_persisted_jobs()
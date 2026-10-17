# -*- coding: utf-8 -*-
"""发布器注册表：国内平台走 Selenium 自动化，海外平台走 Upload-Post API。

新增国内平台：实现 publish(video_path, title, tags, log) 后注册进 PUBLISHERS。
新增海外平台：在 upload_post.PLATFORM_MAP 与 UPLOAD_POST_PLATFORMS 中补充映射。
"""
from . import upload_post
from .douyin import publish as douyin
from .kuaishou import publish as kuaishou
from .shipinhao import publish as shipinhao
from .wechat_mp import publish as wechat_mp

PUBLISHERS = {
    "douyin": douyin,
    "kuaishou": kuaishou,
    "shipinhao": shipinhao,
    "wechat_mp": wechat_mp,
}

UPLOAD_POST_PLATFORMS = {"youtube": "youtube", "instagram": "instagram", "x": "x"}
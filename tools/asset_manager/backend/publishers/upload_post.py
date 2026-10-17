# -*- coding: utf-8 -*-
"""海外平台发布器：通过 Upload-Post API 上传到 YouTube / Instagram / X。"""
import requests

API_URL = "https://api.upload-post.com/api/upload"

# 本地平台名 -> Upload-Post 平台名（platform[] 字段用法与 MoneyPrinterTurbo 一致）
PLATFORM_MAP = {"youtube": "youtube", "instagram": "instagram", "x": "x"}


def publish(platforms, video_path, title, api_key, user, log):
    """单次请求上传到多个平台，返回 {平台名: 状态}。"""
    data = [("user", user), ("title", title[:2200])]
    for p in platforms:
        data.append(("platform[]", PLATFORM_MAP[p]))
    result = {p: "failed" for p in platforms}
    try:
        with open(video_path, "rb") as video_file:
            resp = requests.post(
                API_URL,
                headers={"Authorization": f"Apikey {api_key}"},
                data=data,
                files={"video": video_file},
                timeout=300,
            )
        resp.raise_for_status()
        body = resp.json()
    except requests.RequestException as e:
        log(f"Upload-Post 请求异常：{e}")
        return result
    if body.get("success"):
        log(f"Upload-Post 上传成功，request_id: {body.get('request_id', '')}")
        for p in platforms:
            result[p] = "success"
    else:
        log(f"Upload-Post 上传失败：{body.get('message', body)}")
    return result
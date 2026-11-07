"""微信推送器

支持两种通道：
1. Server酱 (https://sct.ftqq.com) - 简单，免费版每天 5 条
2. 企业微信自建应用 (https://work.weixin.qq.com) - 完全免费，无次数限制

优先推荐企业微信通道。
"""
from __future__ import annotations

import json
import time
from typing import Any

import requests


# ============ Server酱 ============

def send_serverchan(send_key: str, title: str, content: str) -> bool:
    """通过 Server酱 发送微信通知（免费版每天 5 条，订阅版无限）"""
    if not send_key:
        print("[serverchan] 未配置 send_key，跳过")
        return False

    try:
        resp = requests.post(
            f"https://sctapi.ftqq.com/{send_key}.send",
            data={"title": title, "desp": content},
            timeout=15,
        )
        data = resp.json()
        if data.get("code") == 0:
            print("[serverchan] 发送成功")
            return True
        print(f"[serverchan] 发送失败: {data}")
        return False
    except Exception as exc:
        print(f"[serverchan] 异常: {exc}")
        return False


# ============ 企业微信 ============

def _wecom_get_access_token(corpid: str, corpsecret: str) -> str | None:
    """获取企业微信 access_token"""
    try:
        resp = requests.get(
            "https://qyapi.weixin.qq.com/cgi-bin/gettoken",
            params={"corpid": corpid, "corpsecret": corpsecret},
            timeout=15,
        )
        data = resp.json()
        if data.get("errcode") == 0:
            return data["access_token"]
        print(f"[wecom] 获取 access_token 失败: {data}")
        return None
    except Exception as exc:
        print(f"[wecom] 异常: {exc}")
        return None


def _wecom_send_markdown(
    access_token: str, agentid: str, content: str, touser: str = "@all"
) -> bool:
    """通过企业微信发送 markdown 消息"""
    try:
        resp = requests.post(
            "https://qyapi.weixin.qq.com/cgi-bin/message/send",
            params={"access_token": access_token},
            json={
                "touser": touser,
                "msgtype": "markdown",
                "agentid": int(agentid),
                "markdown": {"content": content},
                "safe": 0,
            },
            timeout=15,
        )
        data = resp.json()
        if data.get("errcode") == 0:
            print("[wecom] 发送成功")
            return True
        print(f"[wecom] 发送失败: {data}")
        return False
    except Exception as exc:
        print(f"[wecom] 异常: {exc}")
        return False


def send_wecom(
    corpid: str,
    agentid: str,
    corpsecret: str,
    title: str,
    markdown_content: str,
    touser: str = "@all",
) -> bool:
    """通过企业微信自建应用发送 markdown 通知"""
    if not (corpid and agentid and corpsecret):
        print("[wecom] 未配置完整参数，跳过")
        return False

    token = _wecom_get_access_token(corpid, corpsecret)
    if not token:
        return False

    # 企业微信 markdown 不支持单独的 title，把 title 拼到内容前面
    full_content = f"**{title}**\n\n{markdown_content}"
    return _wecom_send_markdown(token, agentid, full_content, touser)


# ============ 统一入口 ============

def build_wechat_markdown(
    artworks_with_commentary: list[dict[str, Any]],
    date_str: str,
    theme: str,
    image_url_template: str = "",
) -> tuple[str, str]:
    """生成微信推送用的标题和 markdown 内容

    图片优先使用图源官方直链；image_url_template 仅保留用于兼容旧调用方。
    """
    title = f"【审美日课 · {date_str}】{theme}"

    lines: list[str] = []
    lines.append(f"> {theme}")
    lines.append("")
    lines.append(f"今日精选 {len(artworks_with_commentary)} 张作品 👇")
    lines.append("")

    for i, item in enumerate(artworks_with_commentary, 1):
        artwork = item["artwork"]
        style = artwork.get("style", "艺术")
        title_a = artwork.get("title", "")
        artist = artwork.get("artist", "")
        date_a = artwork.get("date", "")
        commentary = item.get("commentary", "")
        local_path = artwork.get("local_path", "")
        extra = artwork.get("extra") or {}

        lines.append(f"### {i}. [{style}] {title_a}")
        if artist or date_a:
            meta = " · ".join([s for s in [artist, date_a] if s])
            lines.append(f"<font color=\"comment\">{meta}</font>")
        lines.append("")

        # 官方直链优先：Unsplash 必须热链，Met / NASA 用官方地址
        direct_url = artwork.get("image_url", "")
        if direct_url:
            lines.append(f"![作品]({direct_url})")
        elif image_url_template and local_path:
            lines.append(f"![作品]({image_url_template.replace('{path}', local_path)})")
        lines.append("")
        lines.append(f"{commentary}")
        lines.append("")

        # Unsplash API Guidelines：署名 + 带 utm 的回链
        if artwork.get("source") == "unsplash":
            photo_url = extra.get("photo_page_url") or "https://unsplash.com"
            profile_url = extra.get("photographer_url") or photo_url
            name = artist or "Unsplash 摄影师"
            lines.append(f"照片来自 [Unsplash]({photo_url}) · 摄影师 [{name}]({profile_url})")
            lines.append("")

        lines.append("---")
        lines.append("")

    lines.append("📚 来自「每日审美推送」 · 每天留两分钟给一张图")
    return title, "\n".join(lines)


def send(
    channel: str,
    config: dict[str, Any],
    title: str,
    content: str,
    markdown_for_wecom: str | None = None,
) -> bool:
    """统一推送入口

    channel: "serverchan" | "wecom"
    config: 对应通道的配置
    markdown_for_wecom: 企业微信专用 markdown 文本（可选）
    """
    if channel == "serverchan":
        return send_serverchan(
            send_key=config.get("serverchan_send_key", ""),
            title=title,
            content=content,
        )
    if channel == "wecom":
        wc = config.get("wecom", {})
        return send_wecom(
            corpid=wc.get("corpid", ""),
            agentid=wc.get("agentid", ""),
            corpsecret=wc.get("corpsecret", ""),
            title=title,
            markdown_content=markdown_for_wecom or content,
        )
    print(f"[wechat] 未知通道: {channel}")
    return False
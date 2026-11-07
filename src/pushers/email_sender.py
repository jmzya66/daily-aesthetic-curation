"""邮件发送器

支持任意 SMTP 服务（QQ邮箱、Gmail、Resend SMTP 等）。
HTML 模板通过 Jinja2 渲染。
"""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


SOURCE_LABELS = {
    "met": "纽约大都会艺术博物馆 Open Access (CC0)",
    "unsplash": "Unsplash（图片经 API 热链展示）",
    "nasa": "NASA Astronomy Picture of the Day",
}


def _source_label(source: str) -> str:
    return SOURCE_LABELS.get(source, source)


def _build_attribution(artwork: dict[str, Any]) -> dict[str, str] | None:
    """Unsplash API Guidelines 要求的署名：Unsplash + 摄影师 + 带 utm 的回链"""
    if artwork.get("source") != "unsplash":
        return None
    extra = artwork.get("extra") or {}
    return {
        "service": "Unsplash",
        "photographer": artwork.get("artist") or "Unsplash 摄影师",
        "photo_url": extra.get("photo_page_url", "") or "https://unsplash.com",
        "profile_url": extra.get("photographer_url", "") or "https://unsplash.com",
    }


def _build_cards(artworks_with_commentary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把 Artwork + 讲解组装成模板用的卡片 dict

    图片一律使用图源官方直链：
      - Unsplash 按 API Guidelines 必须热链 photo.urls，不得转存
      - Met / NASA 为公共领域，可直连官方 URL
    推送不依赖仓库 commit 与 CDN 缓存；归档下载只用于历史回溯。
    """
    cards = []
    for item in artworks_with_commentary:
        artwork = item["artwork"]
        image_url = artwork.get("image_url") or artwork.get("image_url_large") or ""
        cards.append({
            "style": artwork.get("style", "艺术"),
            "title": artwork.get("title", ""),
            "artist": artwork.get("artist", ""),
            "date": artwork.get("date", ""),
            "image_url": image_url,
            "commentary": item.get("commentary", ""),
            "source_label": _source_label(artwork.get("source", "")),
            "attribution": _build_attribution(artwork),
        })
    return cards


def render_email(
    artworks_with_commentary: list[dict[str, Any]],
    date_str: str,
    theme: str,
    archive_url: str = "",
    project_url: str = "",
    template_dir: str | Path | None = None,
) -> tuple[str, str]:
    """渲染邮件，返回 (subject, html_body)"""
    if template_dir is None:
        template_dir = Path(__file__).parent.parent.parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("email.html.j2")

    cards = _build_cards(artworks_with_commentary)

    html = template.render(
        date=date_str,
        theme=theme,
        cards=cards,
        archive_url=archive_url or "#",
        project_url=project_url or "#",
    )
    subject = f"【审美日课 · {date_str}】今日 {len(cards)} 张作品"
    return subject, html


def send_email(
    artworks_with_commentary: list[dict[str, Any]],
    date_str: str,
    theme: str,
    smtp_config: dict[str, Any],
    archive_url: str = "",
    project_url: str = "",
    embed_images: bool = False,
    project_root: Path | None = None,
) -> bool:
    """发送邮件

    smtp_config: smtp_host / smtp_port / smtp_ssl / username / password /
                 from_name / to_addrs；缺项时跳过发送而不是抛 KeyError。
    embed_images / project_root 是旧版 cid 内嵌路径的兼容参数，当前直链架构不启用。
    """
    subject, html_body = render_email(
        artworks_with_commentary,
        date_str=date_str,
        theme=theme,
        archive_url=archive_url,
        project_url=project_url,
    )

    username = smtp_config.get("username") or ""
    password = smtp_config.get("password") or ""
    to_addrs = smtp_config.get("to_addrs") or []
    if isinstance(to_addrs, str):
        to_addrs = [x.strip() for x in to_addrs.split(",") if x.strip()]

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{smtp_config.get('from_name', '审美日课')} <{username}>"
    msg["To"] = ", ".join(to_addrs)
    msg["Date"] = formatdate(localtime=True)
    msg.set_content(
        f"今日审美日课 · {date_str}\n请使用邮件客户端查看 HTML 内容。\n\n{theme}"
    )
    msg.add_alternative(html_body, subtype="html")

    # 旧版 cid 内嵌路径：当前推送全用官方直链，默认不进此分支
    if embed_images and project_root:
        for item in artworks_with_commentary:
            local_rel = item["artwork"].get("local_path", "")
            if not local_rel:
                continue
            local_abs = project_root / local_rel
            if not local_abs.exists():
                continue
            with open(local_abs, "rb") as f:
                data = f.read()
            msg.get_payload()[1].add_related(
                data, maintype="image", subtype="jpeg", cid=item["cid"],
            )

    if not (to_addrs and username and password):
        print("[email] 缺少收件人 / 账号 / 授权码，跳过发送")
        return False

    host = smtp_config.get("smtp_host") or "smtp.qq.com"
    port = int(smtp_config.get("smtp_port", 465))
    use_ssl = smtp_config.get("smtp_ssl", True)

    try:
        if use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as server:
                server.login(username, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as server:
                server.starttls(context=ssl.create_default_context())
                server.login(username, password)
                server.send_message(msg)
        print(f"[email] 发送成功 -> {to_addrs}")
        return True
    except Exception as exc:
        print(f"[email] 发送失败: {exc}")
        return False
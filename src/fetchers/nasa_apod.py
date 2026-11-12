"""NASA Astronomy Picture of the Day fetcher

API: https://science.nasa.gov/wp-json/wp/v2/apod-basic
特点: 公开 feed、免 API key，一次返回最近约 25 条（JSON 数组）。
      date / start_date / end_date 参数实测不生效，故在本地按日期窗口过滤。
旧端点 api.nasa.gov/planetary/apod 计划 2026-12 归档下线。
"""
from __future__ import annotations

import html
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from ..models import Artwork, download_image, sanitize_filename, short_hash

API_URL = "https://science.nasa.gov/wp-json/wp/v2/apod-basic"


def _clean_html(text: str) -> str:
    """APOD 的 explanation 是含 HTML 的长文本，清洗成纯文本"""
    plain = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", plain).strip()




def _downscale_url(url: str, max_width: int = 1080) -> str:
    """把 NASA dynamicimage 直链的 w/h 参数等比缩到 max_width。

    实测同一张图 w=4144 为 27 MB，w=1080 仅 1.6 MB。仍是官方直链，
    只改尺寸参数；URL 没有合法 w/h 参数时原样返回，避免改坏链接。
    """
    if not url or "?" not in url:
        return url
    base, _, query = url.partition("?")
    params: dict[str, str] = {}
    order: list[str] = []
    for part in query.split("&"):
        if not part:
            continue
        k, sep, v = part.partition("=")
        if k not in params:
            order.append(k)
        params[k] = v if sep else ""
    try:
        w, h = int(params["w"]), int(params["h"])
    except (KeyError, TypeError, ValueError):
        return url
    if w <= max_width:
        return url
    params["w"] = str(max_width)
    params["h"] = str(max(1, round(h * max_width / w)))
    return base + "?" + "&".join(
        f"{k}={params[k]}" if params[k] else k for k in order
    )


def fetch(
    lookback_days: int = 30,
    max_pick: int = 1,
) -> list[Artwork]:
    """一次请求取回最近约 25 条 APOD，按日期窗口过滤后随机抽 max_pick 张。

    不再逐日串行请求 30 次（旧端点 DEMO_KEY 限 30 次/小时会撞限流），
    也不再依赖 api_key。只收 media_type=image 的条目。
    """
    try:
        resp = requests.get(
            API_URL,
            params={"count": 30},
            headers={"User-Agent": "Mozilla/5.0 (compatible; AestheticDailyBot/1.0)"},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            data = [data]
        print(f"[nasa] feed 返回 {len(data)} 条")
    except Exception as exc:
        print(f"[nasa] ⚠️ feed 获取失败（{API_URL}）: {exc}")
        return []

    cutoff = (datetime.now(timezone(timedelta(hours=8)))
              - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    candidates = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if item.get("media_type") != "image" or not item.get("url"):
            continue
        d = item.get("date", "")
        if d and d < cutoff:
            continue
        candidates.append(item)

    if not candidates:
        print(f"[nasa] ⚠️ {len(data)} 条里没有落在 {cutoff} 之后的可用图片（该图源本次缺席）")
        return []

    picks = random.sample(candidates, min(max_pick, len(candidates)))
    results: list[Artwork] = []
    for pick in picks:
        explanation = _clean_html(pick.get("explanation", ""))
        img_url = _downscale_url(pick.get("hdurl") or pick.get("url", ""))
        results.append(
            Artwork(
                source="nasa",
                source_id=pick.get("date") or str(pick.get("post_id", "")),
                title=pick.get("title") or "Untitled",
                # feed 的 copyright / credit 常含 <a href>，不清洗会在邮件与微信里显示成字面标签
                artist=_clean_html(pick.get("copyright") or pick.get("credit") or "") or "NASA",
                date=pick.get("date", ""),
                style="天文",
                description=explanation[:300],
                # 实测：feed 的 url 常返回 text/html 页面，hdurl 才是真图片。
                # 展示与归档都用缩放后的 hdurl（w<=1080），避免单张几十 MB。
                image_url=img_url,
                image_url_large=img_url,
                extra={
                    "apod_date": pick.get("date", ""),
                    "explanation_full": explanation,
                    "permalink": pick.get("permalink", ""),
                    "credit": _clean_html(pick.get("credit", "")),
                    "alt": pick.get("alt", ""),
                },
            )
        )
    return results


def download(artwork: Artwork, dest_dir: Path) -> Artwork:
    """下载 APOD 图片归档（必须用 hdurl；url 是 HTML 页面）"""
    if not artwork.image_url:
        return artwork

    safe = sanitize_filename(artwork.title or "apod")
    filename = f"{artwork.source}_{artwork.source_id}_{short_hash(artwork.title)}.jpg"
    local = download_image(artwork.image_url_large or artwork.image_url, dest_dir, filename)

    if local:
        artwork.local_path = str(local.relative_to(dest_dir.parent.parent))
    else:
        print(f"[nasa] ⚠️ 图片下载失败，无本地归档: {artwork.image_url_large or artwork.image_url}")
    return artwork
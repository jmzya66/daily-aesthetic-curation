"""NASA Astronomy Picture of the Day fetcher

API: https://api.nasa.gov/planetary/apod
特点: 每日一张天文图 + 专业讲解，DEMO_KEY 限 30 req/h/IP
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import requests

from ..models import Artwork, download_image, sanitize_filename, short_hash

API_URL = "https://api.nasa.gov/planetary/apod"


def fetch(
    api_key: str = "DEMO_KEY",
    lookback_days: int = 30,
    max_pick: int = 1,
) -> list[Artwork]:
    """从 NASA APOD 抽取最近 lookback_days 天内的一张图

    NASA APOD 每天只有一张图，为了让内容不重复，我们从最近一段时间里随机选一天
    """
    end = datetime.now()
    start = end - timedelta(days=lookback_days)

    # APOD 实际只能一次拿一天，用 thumbs API 一次拿多天
    # 但 thumbs 在某些情况下不稳，我们直接循环拿最近 N 天
    candidates = []
    for i in range(lookback_days):
        d = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        try:
            resp = requests.get(
                API_URL,
                params={"api_key": api_key, "date": d, "thumbs": True},
                timeout=15,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            # 只收图片，不收视频
            if data.get("media_type") != "image":
                continue
            candidates.append(data)
        except Exception as exc:
            print(f"[nasa] 获取 {d} 失败: {exc}")
            continue

    if not candidates:
        return []

    pick = random.choice(candidates)
    return [
        Artwork(
            source="nasa",
            source_id=pick.get("date", ""),
            title=pick.get("title", "Untitled"),
            artist=pick.get("copyright", "NASA"),
            date=pick.get("date", ""),
            style="天文",
            description=pick.get("explanation", "")[:300],
            image_url=pick.get("url", ""),
            image_url_large=pick.get("hdurl", pick.get("url", "")),
            extra={
                "apod_date": pick.get("date", ""),
                "explanation_full": pick.get("explanation", ""),
                "service_version": pick.get("service_version", ""),
            },
        )
    ][:max_pick]


def download(artwork: Artwork, dest_dir: Path) -> Artwork:
    """下载 APOD 图（用高清版本）"""
    if not artwork.image_url:
        return artwork

    safe = sanitize_filename(artwork.title or "apod")
    filename = f"{artwork.source}_{artwork.source_id}_{short_hash(artwork.title)}.jpg"
    # APOD hdurl 可能很大，单独下载高清版
    if artwork.image_url_large:
        local = download_image(artwork.image_url_large, dest_dir, filename)
    else:
        local = download_image(artwork.image_url, dest_dir, filename)

    if local:
        artwork.local_path = str(local.relative_to(dest_dir.parent.parent))
    return artwork
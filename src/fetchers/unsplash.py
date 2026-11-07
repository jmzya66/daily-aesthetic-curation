"""Unsplash fetcher (摄影图源)

API: https://unsplash.com/developers
额度: demo 模式 50 次/小时；通过审核的生产模式 1000 次/小时

合规约定（Unsplash API Guidelines）：
  - 通过 API 取得的图片必须热链官方 photo.urls，不得下载转存到自有仓库或 CDN
  - 展示时必须署名 Unsplash 与摄影师，回链带 utm 参数
因此本 fetcher 不落盘，只在 extra 里带齐署名所需字段。
"""
from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import requests

from ..models import Artwork

API_BASE = "https://api.unsplash.com"
UTM_SUFFIX = "utm_source=daily_aesthetic_curation&utm_medium=referral"


def _with_utm(url: str) -> str:
    """给 Unsplash 回链加上官方要求的 utm 参数"""
    if not url:
        return ""
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{UTM_SUFFIX}"


def fetch(
    access_key: str,
    queries: list[str] | None = None,
    orientation: str = "landscape",
    per_page: int = 30,
    max_pick: int = 1,
) -> list[Artwork]:
    """从 Unsplash 按关键词随机抽取摄影作品"""
    if not access_key:
        print("[unsplash] 未提供 access_key，跳过")
        return []

    query_list = queries or ["nature", "architecture", "abstract", "minimal"]
    query = random.choice(query_list)

    headers = {"Authorization": f"Client-ID {access_key}"}
    params: dict[str, Any] = {
        "query": query,
        "orientation": orientation,
        "per_page": per_page,
        "content_filter": "high",
    }

    # 优先尝试用 /photos/random，按 query 抽
    try:
        resp = requests.get(
            f"{API_BASE}/photos/random",
            headers=headers,
            params={**params, "count": max_pick * 5},
            timeout=20,
        )
        resp.raise_for_status()
        photos = resp.json()
        if not isinstance(photos, list):
            photos = [photos]
    except Exception as exc:
        print(f"[unsplash] /photos/random 失败，回退到 /search: {exc}")
        resp = requests.get(
            f"{API_BASE}/search/photos",
            headers=headers,
            params=params,
            timeout=20,
        )
        resp.raise_for_status()
        all_results = resp.json().get("results", [])
        photos = random.sample(all_results, min(max_pick * 5, len(all_results)))

    results: list[Artwork] = []
    for photo in photos:
        if len(results) >= max_pick:
            break

        user = photo.get("user", {})
        links = photo.get("links", {}) or {}
        results.append(
            Artwork(
                source="unsplash",
                source_id=photo["id"],
                title=photo.get("alt_description") or photo.get("description") or "Untitled",
                artist=user.get("name", "Unknown"),
                date=photo.get("created_at", "")[:10] if photo.get("created_at") else "",
                style="摄影",
                description=(photo.get("alt_description") or "")[:200],
                image_url=photo.get("urls", {}).get("regular", ""),
                image_url_large=photo.get("urls", {}).get("full", ""),
                extra={
                    "delivery": "hotlink",
                    "query": query,
                    "color": photo.get("color", ""),
                    "location": user.get("location", ""),
                    "portfolio_url": user.get("links", {}).get("html", ""),
                    "photo_page_url": _with_utm(links.get("html", "")),
                    "photographer_url": _with_utm(user.get("links", {}).get("html", "")),
                    "download_location": links.get("download_location", ""),
                    "tags": [t["title"] for t in photo.get("tags", []) if t.get("title")],
                    "width": photo.get("width"),
                    "height": photo.get("height"),
                },
            )
        )

    return results


def download(artwork: Artwork, dest_dir: Path) -> Artwork:
    """Unsplash 图片按 API Guidelines 只热链、不下载落盘。

    保留此函数以维持 fetcher 接口一致（main.py 对所有图源统一调用 download）。
    热链源没有 local_path，调用方必须按 extra.delivery 判断，不能按 local_path 过滤。
    """
    artwork.extra["delivery"] = "hotlink"
    artwork.local_path = ""
    return artwork
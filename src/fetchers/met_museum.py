"""Met Museum Open Access fetcher

API: https://collectionapi.metmuseum.org/public/collection/v1/
特点: 无需 API key，CC0 协议，约 47 万件作品
"""
from __future__ import annotations

import random
from pathlib import Path

import requests

from ..models import Artwork, download_image, short_hash, sanitize_filename

API_BASE = "https://collectionapi.metmuseum.org/public/collection/v1"


def _search_object_ids(
    department_ids: list[int] | None = None,
    sample_size: int = 80,
    query: str | None = None,
) -> list[int]:
    """用 /search 接口一次拿到符合条件（有图+公共领域）的 ID 列表

    比逐条请求 /objects/{id} 快几个数量级
    """
    params: dict = {
        "hasImages": "true",
        "isPublicDomain": "true",
    }
    if query:
        params["q"] = query
    if department_ids:
        # search 支持单个 departmentId，多部门要多次请求合并
        if len(department_ids) == 1:
            params["departmentId"] = department_ids[0]

    # 加重试 + 多个 query fallback
    queries_to_try = [query] if query else ["painting", "oil", "art", None]
    for q in queries_to_try:
        for attempt in range(2):
            try:
                if q:
                    params["q"] = q
                elif "q" in params:
                    del params["q"]
                resp = requests.get(f"{API_BASE}/search", params=params, timeout=30)
                resp.raise_for_status()
                obj_ids = resp.json().get("objectIDs") or []
                if obj_ids:
                    return random.sample(obj_ids, min(sample_size, len(obj_ids)))
            except Exception as exc:
                print(f"[met] search(q={q!r}) 失败（重试 {attempt+1}/2）: {exc}")
                continue

    return []


def fetch(
    department_ids: list[int] | None = None,
    sample_size: int = 80,
    max_pick: int = 1,
    query: str | None = None,
) -> list[Artwork]:
    """从 Met Museum 抽取作品

    步骤: /search 一次性拿到符合 hasImages + isPublicDomain 的 ID 列表 →
          随机抽样 → 逐条请求详情 → 拼装成 Artwork
    """
    obj_ids = _search_object_ids(
        department_ids=department_ids,
        sample_size=sample_size,
        query=query,
    )
    if not obj_ids:
        return []

    # 抽样 max_pick * 3 个，逐个请求详情（成功率约 95%+）
    picks = random.sample(obj_ids, min(max_pick * 3, len(obj_ids)))
    results: list[Artwork] = []
    for oid in picks:
        if len(results) >= max_pick:
            break
        try:
            resp = requests.get(f"{API_BASE}/objects/{oid}", timeout=15)
            resp.raise_for_status()
            obj = resp.json()
            if not obj.get("primaryImage"):
                continue

            artwork = Artwork(
                source="met",
                source_id=str(obj["objectID"]),
                title=obj.get("title") or "Untitled",
                artist=obj.get("artistDisplayName") or "Unknown",
                date=str(obj.get("objectDate") or obj.get("objectBeginDate", "")),
                style="古典艺术",
                description=obj.get("medium") or "",
                image_url=obj.get("primaryImage", ""),
                image_url_large=obj.get("primaryImage", ""),
                extra={
                    "department": obj.get("department", ""),
                    "culture": obj.get("culture", ""),
                    "period": obj.get("period", ""),
                    "medium": obj.get("medium", ""),
                    "dimensions": obj.get("dimensions", ""),
                    "creditLine": obj.get("creditLine", ""),
                    "tags": obj.get("tags", []) or [],
                },
            )
            results.append(artwork)
        except Exception as exc:
            print(f"[met] 获取 object {oid} 失败: {exc}")
            continue

    return results


def download(artwork: Artwork, dest_dir: Path) -> Artwork:
    """下载作品原图，返回更新过 local_path 的 Artwork"""
    if not artwork.image_url:
        return artwork

    safe_name = sanitize_filename(artwork.title or "untitled")
    filename = f"{artwork.source}_{safe_name}_{short_hash(artwork.source_id)}.jpg"
    local = download_image(artwork.image_url, dest_dir, filename)
    if local:
        # 存相对路径，便于邮件和归档
        artwork.local_path = str(local.relative_to(dest_dir.parent.parent))
    return artwork
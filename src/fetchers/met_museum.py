"""Met Museum Open Access fetcher

API: https://collectionapi.metmuseum.org/public/collection/v1/
特点: 无需 API key，CC0 协议，约 50 万件作品
注意: /search 已于 2026-11 整体返回 410 Gone，本项目改用 /objects 全量 ID 池抽样
"""
from __future__ import annotations

import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from ..models import Artwork, download_image, short_hash, sanitize_filename

API_BASE = "https://collectionapi.metmuseum.org/public/collection/v1"


def _object_id_pool(sample_size: int = 20) -> list[int]:
    """从 /objects 全量 ID 列表随机抽样。

    2026-11 实测：/search 端点整体 410 Gone（带不带参数都一样），但 /objects
    仍返回约 50 万条 objectIDs。该端点不支持 departmentId / hasImages /
    isPublicDomain 过滤（参数被忽略），所以命中率靠后续详情请求校验：
    本机抽样 40 个 ID，约 55% 有 primaryImage 且为公共领域。
    """
    try:
        resp = requests.get(f"{API_BASE}/objects", timeout=30)
        resp.raise_for_status()
        ids = resp.json().get("objectIDs") or []
    except Exception as exc:
        print(f"[met] ⚠️ /objects 取全量 ID 失败: {exc}")
        return []
    if not ids:
        print("[met] ⚠️ /objects 返回空 ID 列表")
        return []
    print(f"[met] /objects 拿到 {len(ids)} 个 ID，抽样 {min(sample_size, len(ids))} 个")
    return random.sample(ids, min(sample_size, len(ids)))


def fetch(
    department_ids: list[int] | None = None,
    sample_size: int = 80,
    max_pick: int = 1,
    query: str | None = None,
) -> list[Artwork]:
    """从全量 ID 池抽样，并发请求详情，收够 max_pick 张有图作品。

    sample_size / department_ids / query 保留用于兼容旧调用，但 /objects
    端点不支持过滤，实际抽样量按 max_pick 计算。
    """
    if department_ids or query:
        print("[met] 提示：/objects 不支持部门/关键词过滤，本次忽略这些条件")
    pool_size = min(max(12, max_pick * 10), 40)
    obj_ids = _object_id_pool(sample_size=pool_size)
    if not obj_ids:
        return []

    def load_one(oid: int) -> Artwork | None:
        try:
            resp = requests.get(f"{API_BASE}/objects/{oid}", timeout=15)
            resp.raise_for_status()
            obj = resp.json()
            if not obj.get("primaryImage"):
                return None
            return Artwork(
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
        except Exception as exc:
            print(f"[met] object {oid} 获取失败: {exc}")
            return None

    results: list[Artwork] = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        for aw in ex.map(load_one, obj_ids):
            if aw is None:
                continue
            results.append(aw)
            if len(results) >= max_pick:
                break
    if not results:
        print(f"[met] ⚠️ 抽样 {len(obj_ids)} 个 ID 后仍无可用作品（该图源本次缺席）")
    return results[:max_pick]


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
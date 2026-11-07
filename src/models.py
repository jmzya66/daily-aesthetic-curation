"""每日审美推送 - 共享数据结构与工具"""
from __future__ import annotations

import os
import re
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


@dataclass
class Artwork:
    """统一的作品数据结构（来自任意图源）"""
    source: str                              # 图源标识: met | unsplash | nasa
    source_id: str                           # 图源中的唯一 ID
    title: str
    artist: str = ""                         # 作者/版权方
    date: str = ""                           # 创作年代/发布日
    style: str = ""                          # 风格标签：古典艺术 / 摄影 / 天文 等
    description: str = ""                    # 原系统给的简介
    image_url: str = ""                      # 原图 URL
    image_url_large: str = ""                # 高清图 URL
    local_path: str = ""                     # 下载到本地后的相对路径
    extra: dict[str, Any] = field(default_factory=dict)  # 其它元数据

    def stable_key(self) -> str:
        """用于跨天去重的稳定键"""
        return f"{self.source}:{self.source_id}"


def sanitize_filename(name: str, fallback: str = "artwork") -> str:
    """生成安全的文件名（去除非法字符）"""
    name = re.sub(r"[^\w\-\.]+", "_", name.strip())
    name = re.sub(r"_+", "_", name)
    return name[:80] or fallback


def short_hash(text: str, length: int = 8) -> str:
    """对字符串生成短哈希，用于文件名去重"""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:length]


def today_str() -> str:
    """返回 YYYY-MM-DD 格式的今天"""
    return datetime.now().strftime("%Y-%m-%d")


def download_image(
    url: str,
    dest_dir: Path,
    filename: str,
    timeout: int = 30,
    min_bytes: int = 1024,
) -> Path | None:
    """下载远程图片到本地目录，返回本地路径，失败返回 None"""
    if not url:
        return None

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename

    try:
        # Unsplash 等可能要求 UA
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; AestheticDailyBot/1.0)",
            "Accept": "image/*",
        }
        resp = requests.get(url, headers=headers, timeout=timeout, stream=True)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            print(f"[download] 非图片内容，跳过: {url} ({content_type})")
            return None

        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        if dest_path.stat().st_size < min_bytes:
            print(f"[download] 文件过小，跳过: {dest_path}")
            dest_path.unlink(missing_ok=True)
            return None

        return dest_path

    except Exception as exc:
        print(f"[download] 下载失败 {url}: {exc}")
        return None


def ensure_dir(path: str | Path) -> Path:
    """确保目录存在，返回 Path 对象"""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
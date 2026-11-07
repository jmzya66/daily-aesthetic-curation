"""AI 审美讲解生成器

调用 OpenAI 兼容接口（DeepSeek / OpenAI / Azure 都可）的 LLM，
基于作品元数据生成 50-80 字的中文审美笔记。

失败时返回 fallback 文案，不阻塞整体流程。
"""
from __future__ import annotations

import os
from typing import Any

import requests


SYSTEM_PROMPT = """你是一位耐心且有审美直觉的艺术教育者，正在为一位希望每天提升审美能力的普通人写「每日审美笔记」。
你擅长用具体可感知的词汇描述作品，避免空洞的赞美词（如"美轮美奂""巧夺天工"）。
你的讲解让初学者看完会觉得「哦，原来我也可以这样去看一张图」。"""


USER_PROMPT_TEMPLATE = """请基于以下作品信息写一段 50-80 字的中文「审美笔记」，目标是让读者看懂这张图美在哪里。

【作品信息】
标题：{title}
作者：{artist}
年代：{date}
媒介/类型：{medium}
风格标签：{tags}
来源：{source}
补充描述：{description}

【讲解应包含】（不必逐条对应，自然融入）
1. 第一眼看到什么（视觉冲击点）
2. 用什么手法达到这种效果（构图/色彩/光影/笔触/材料 等）
3. 一个值得借鉴或思考的小点（可以是一个反问）

【写作要求】
- 用具体词汇，避免"美轮美奂""巧夺天工"等空话
- 不要用"这幅作品""此画"等套话开头
- 50-80 字之间，不要分点列举，写成一段流畅的话
- 不需要标题，直接输出正文
- 如果信息太少，就聚焦"色彩"或"构图"一个点深入讲"""


def _format_metadata(artwork_dict: dict[str, Any]) -> dict[str, str]:
    """把 Artwork 转成 LLM 输入用的字段"""
    extra = artwork_dict.get("extra") or {}
    tags = extra.get("tags") or []
    if isinstance(tags, list):
        tag_str = "、".join(str(t) for t in tags[:5])
    else:
        tag_str = str(tags)

    return {
        "title": artwork_dict.get("title", ""),
        "artist": artwork_dict.get("artist", ""),
        "date": artwork_dict.get("date", ""),
        "medium": extra.get("medium") or artwork_dict.get("description", ""),
        "tags": tag_str or artwork_dict.get("style", ""),
        "source": artwork_dict.get("source", ""),
        "description": artwork_dict.get("description", ""),
    }


def generate_commentary(
    artwork_dict: dict[str, Any],
    api_key: str,
    base_url: str = "https://api.deepseek.com/v1",
    model: str = "deepseek-chat",
    timeout: int = 30,
) -> str:
    """为单个作品生成审美讲解；失败时返回兜底文本"""
    meta = _format_metadata(artwork_dict)
    user_prompt = USER_PROMPT_TEMPLATE.format(**meta)

    if not api_key:
        return _fallback(artwork_dict)

    try:
        resp = requests.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 300,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        return content[:300]  # 保险截断
    except Exception as exc:
        print(f"[llm] 讲解生成失败: {exc}")
        return _fallback(artwork_dict)


def generate_batch(
    artworks: list[dict[str, Any]],
    api_key: str,
    base_url: str = "https://api.deepseek.com/v1",
    model: str = "deepseek-chat",
) -> list[str]:
    """批量生成讲解，按输入顺序返回"""
    return [generate_commentary(a, api_key, base_url, model) for a in artworks]


def _fallback(artwork_dict: dict[str, Any]) -> str:
    """LLM 不可用时的兜底文案（保证不空）"""
    style = artwork_dict.get("style", "")
    title = artwork_dict.get("title", "")
    artist = artwork_dict.get("artist", "")
    return (
        f"今日精选：{style}作品《{title}》"
        f"{'——' + artist if artist else ''}。"
        f"试着眯起眼看整体轮廓，再聚焦一处细节——这是入门审美的两个开关。"
    )
"""观察笔记生成器（默认离线，LLM 为可选分支）

当前默认不接 LLM：按「当日审美维度 + 作品元数据」离线拼装 50-80 字中文观察笔记，
零依赖、可复现、每张不同。显式配置 api_key 时才改走原来的 OpenAI 兼容接口。
"""
from __future__ import annotations

import hashlib
import html
import re
from typing import Any

import requests

# 与 main._pick_theme() 的 7 条主题一一对应（按 weekday 轮换）
DIMENSION_KEYS = ["构图", "色彩", "光影", "质感", "情绪", "细节", "历史"]

OBSERVATION_LINES: dict[str, list[str]] = {
    "构图": [
        "先别看主体，找画面里最重的那一块，看它把视线推向哪里。",
        "眯起眼只看大轮廓，数数留白占了多大、又留给了谁。",
        "把画面横竖各切一刀，比一比四条边的重量是不是平衡。",
        "找一条藏起来的对角线，很多安排都压在这条线上。",
    ],
    "色彩": [
        "先说出第一眼抓住你的颜色，再找它的补色躲在哪。",
        "分一分冷暖：暖色往往往前跑，冷色通常往后退。",
        "找画面里最不起眼的那块灰，它常是让颜色不吵架的关键。",
        "数数全画用了几种颜色，少不一定寡淡，多也不一定热闹。",
    ],
    "光影": [
        "先猜光源在画面外的哪个方向，再看影子对不对得上。",
        "留意最暗的地方：暗不是没画，是用来把亮处托起来的。",
        "找一处渐变最慢的过渡，那里藏着作者对材质的判断。",
        "比一比最亮与最暗的差距，反差越大，情绪通常越紧。",
    ],
    "质感": [
        "靠近看笔触的方向，它比形状更容易暴露作画时的手势。",
        "找一处边缘：是利落切断，还是慢慢化开，手感完全不同。",
        "想象伸手摸上去是什么温度、什么粗糙度，再看画面支不支持。",
        "留意颗粒与纹理，它们是让平面显得可信的小证据。",
    ],
    "情绪": [
        "先别分析，记下第一秒的身体反应：是想靠近还是想退开。",
        "给这张图一个情绪词，再找画面里替你作证的那个细节。",
        "看久一点，留意情绪会不会从最初那个慢慢漂移。",
        "如果配一段音乐，你会选什么速度？答案往往就是画面的节奏。",
    ],
    "细节": [
        "从四个角落各看十秒，作者常把最放松的笔放在那里。",
        "找一处重复出现的小形状，它多半不是巧合。",
        "找签名、日期或题跋，位置本身也是构图的一部分。",
        "挑一个你觉得「没必要画」的东西，想想它为什么还在。",
    ],
    "历史": [
        "记住创作年代，想想那一年别处正在发生什么。",
        "看材料与尺寸：它原本是挂在墙上，还是拿在手里翻的？",
        "猜猜最初是谁订的、给谁看的，用途会影响画面怎么组织。",
        "对比今天的同类题材，哪些做法留下了，哪些悄悄消失了。",
    ],
}


def _clean_text(text: str, limit: int = 120) -> str:
    """去掉 HTML 标签与多余空白（APOD 的 explanation 含 HTML）"""
    plain = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", plain).strip()[:limit]


def _dimension(theme: str) -> str:
    """从当日主题里取出审美维度"""
    for key in DIMENSION_KEYS:
        if key in (theme or ""):
            return key
    return DIMENSION_KEYS[0]


def _pick_line(dim: str, artwork: dict[str, Any]) -> str:
    """按 source:source_id 稳定取一条，保证同一作品每次一致、不同作品尽量分散"""
    pool = OBSERVATION_LINES.get(dim) or OBSERVATION_LINES["构图"]
    seed = f"{artwork.get('source', '')}:{artwork.get('source_id', '')}"
    idx = int(hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8], 16) % len(pool)
    return pool[idx]


def _fact_sentence(artwork: dict[str, Any]) -> str:
    """从图源元数据拼一句可验证的事实，不用空话"""
    extra = artwork.get("extra") or {}
    title = artwork.get("title") or "无题"
    source = artwork.get("source", "")
    if source == "met":
        bits = [b for b in [extra.get("medium") or artwork.get("description", ""),
                            extra.get("culture", ""), extra.get("period", ""),
                            artwork.get("date", "")] if b]
        head = "、".join(_clean_text(str(b), 26) for b in bits[:3]) or "古典艺术"
        return f"《{title}》：{head}。"
    if source == "unsplash":
        bits = [b for b in [extra.get("query", ""), extra.get("color", ""),
                            extra.get("location", "")] if b]
        head = "、".join(str(b) for b in bits[:2]) or "摄影"
        return f"摄影《{title}》，关键词 {head}。"
    if source == "nasa":
        d = artwork.get("date", "")
        return f"{d} 的每日天文图《{title}》。" if d else f"天文图《{title}》。"
    return f"{artwork.get('style', '')}作品《{title}》。"


def build_offline_commentary(artwork: dict[str, Any], theme: str = "") -> str:
    """离线观察笔记 = 事实句 + 当日维度的可操作观察动作"""
    dim = _dimension(theme)
    text = f"{_fact_sentence(artwork)}今日看{dim}：{_pick_line(dim, artwork)}"
    return text[:110]




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
    """把 Artwork 转成 LLM 输入用的字段（仅 LLM 分支使用）"""
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
    api_key: str = "",
    base_url: str = "https://api.deepseek.com/v1",
    model: str = "deepseek-chat",
    theme: str = "",
) -> list[str]:
    """批量生成讲解，按输入顺序返回。

    默认走离线规则化讲解；只有显式配置 api_key 才调用 LLM。
    """
    if api_key:
        return [generate_commentary(a, api_key, base_url, model) for a in artworks]
    return [build_offline_commentary(a, theme) for a in artworks]


def _fallback(artwork_dict: dict[str, Any]) -> str:
    """LLM 调用失败时回落到离线讲解，保证文字不空、不重复"""
    return build_offline_commentary(artwork_dict)
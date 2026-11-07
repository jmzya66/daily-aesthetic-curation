"""每日审美推送 · 主流程

执行顺序：
1. 加载配置 + 环境变量
2. 从多个图源随机抽取 3-5 张不同风格作品
3. Met / NASA 下载原图归档；Unsplash 按 API Guidelines 只热链、不落盘
4. 调用 LLM 生成每张作品的审美讲解
5. 先写归档 index.json（推送失败也保留当天记录）
6. 推送邮件 + 微信（图片一律使用图源官方直链）
7. 标记已推送，更新 INDEX.md

推送图片不依赖 git commit / CDN；归档是历史记录，不是图片的投递通道。
DRY-RUN 只跑 1-5 与 7，不发任何邮件或微信。
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# 让 Python 找到 src 包
ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

from src.models import Artwork, ensure_dir, today_str  # noqa: E402
from src.fetchers import met_museum, unsplash, nasa_apod  # noqa: E402
from src.ai_commentary import generate_batch  # noqa: E402
from src.pushers.email_sender import send_email  # noqa: E402
from src.pushers.wechat_sender import send as send_wechat, build_wechat_markdown  # noqa: E402


# ============ 配置加载 ============

def load_config(path: str | Path = "config.yaml") -> dict[str, Any]:
    """加载 YAML 配置，环境变量优先覆盖

    CI 上通常没有 config.yaml（被 .gitignore 排除），所以所有必填项都必须有
    env 映射或代码内默认值，不能出现裸字典索引。
    """
    path = Path(path)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    else:
        print(f"[config] {path} 不存在，使用默认 + 环境变量")
        cfg = {}

    # 环境变量覆盖（白名单，未列出的变量读不到）
    env_map = {
        "llm.api_key": "LLM_API_KEY",
        "llm.base_url": "LLM_BASE_URL",
        "llm.model": "LLM_MODEL",
        "unsplash.access_key": "UNSPLASH_ACCESS_KEY",
        "nasa_apod.api_key": "NASA_API_KEY",
        "email.smtp_host": "EMAIL_SMTP_HOST",
        "email.smtp_port": "EMAIL_SMTP_PORT",
        "email.username": "EMAIL_USERNAME",
        "email.password": "EMAIL_PASSWORD",
        "email.to_addrs": "EMAIL_TO",
        "wechat.channel": "WECHAT_CHANNEL",
        "wechat.serverchan_send_key": "WECHAT_SENDKEY",
        "wechat.wecom.corpid": "WECOM_CORPID",
        "wechat.wecom.agentid": "WECOM_AGENTID",
        "wechat.wecom.corpsecret": "WECOM_CORPSECRET",
        "schedule.total_cards": "TOTAL_CARDS",
        "repo.base_url": "REPO_BASE_URL",
        "debug.dry_run": "DRY_RUN",
    }
    for dotted, env_name in env_map.items():
        val = os.getenv(env_name)
        if not val:
            continue
        cur = cfg
        parts = dotted.split(".")
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = val

    # EMAIL_TO 是逗号分隔的字符串，转 list
    email_cfg = cfg.get("email")
    if isinstance(email_cfg, dict) and isinstance(email_cfg.get("to_addrs"), str):
        email_cfg["to_addrs"] = [
            x.strip() for x in email_cfg["to_addrs"].split(",") if x.strip()
        ]

    # DRY_RUN 字符串转 bool
    debug_cfg = cfg.get("debug")
    if isinstance(debug_cfg, dict) and isinstance(debug_cfg.get("dry_run"), str):
        debug_cfg["dry_run"] = debug_cfg["dry_run"].lower() in ("1", "true", "yes")

    # 数值型环境变量转 int，避免字符串参与算术或比较
    for section, key in (("schedule", "total_cards"), ("email", "smtp_port")):
        sec = cfg.get(section)
        if isinstance(sec, dict) and isinstance(sec.get(key), str):
            try:
                sec[key] = int(sec[key])
            except ValueError:
                sec.pop(key, None)

    # 微信通道：未显式配置时，按已提供的凭据自动推断
    wechat = cfg.get("wechat")
    if not isinstance(wechat, dict):
        wechat = {}
        cfg["wechat"] = wechat
    if not wechat.get("channel"):
        wc = wechat.get("wecom") or {}
        if wc.get("corpid") and wc.get("agentid") and wc.get("corpsecret"):
            wechat["channel"] = "wecom"
        elif wechat.get("serverchan_send_key"):
            wechat["channel"] = "serverchan"

    return cfg


# ============ 抓图调度 ============

def pick_artworks(cfg: dict[str, Any], total_cards: int) -> list[Artwork]:
    """从多个图源组合抽取 total_cards 张作品"""
    artworks: list[Artwork] = []

    # 配额策略：每个图源至少一张，剩余随机分配
    sources = []
    if cfg.get("met_museum", {}).get("enabled", True):
        sources.append(("met", cfg.get("met_museum", {})))
    if cfg.get("unsplash", {}).get("access_key"):
        sources.append(("unsplash", cfg.get("unsplash", {})))
    if cfg.get("nasa_apod", {}).get("enabled", True):
        sources.append(("nasa", cfg.get("nasa_apod", {})))

    if not sources:
        print("[pick] 没有可用的图源")
        return []

    # 给每个图源基础配额 1，剩余 total_cards - n 个随机分配
    base = 1
    extra = max(0, total_cards - len(sources))
    weights = [base] * len(sources)
    for _ in range(extra):
        weights[random.randint(0, len(sources) - 1)] += 1

    for (name, src_cfg), n in zip(sources, weights):
        try:
            if name == "met":
                picked = met_museum.fetch(
                    department_ids=src_cfg.get("department_ids") or None,
                    max_pick=n,
                )
            elif name == "unsplash":
                picked = unsplash.fetch(
                    access_key=src_cfg.get("access_key", ""),
                    queries=src_cfg.get("queries"),
                    orientation=src_cfg.get("orientation", "landscape"),
                    per_page=src_cfg.get("per_page", 30),
                    max_pick=n,
                )
            elif name == "nasa":
                picked = nasa_apod.fetch(
                    api_key=src_cfg.get("api_key", "DEMO_KEY"),
                    max_pick=n,
                )
            else:
                continue
            print(f"[pick] {name} 抽到 {len(picked)} 张")
            artworks.extend(picked)
        except Exception as exc:
            print(f"[pick] {name} 抓取失败: {exc}")

    # 按某种策略排序：风格多样性优先
    random.shuffle(artworks)
    return artworks[:total_cards]


# ============ 主流程 ============

def _repo_urls(base_url: str) -> tuple[str, str]:
    """从 raw.githubusercontent.com URL 推导历史归档页与项目主页"""
    prefix = "raw.githubusercontent.com/"
    if prefix not in base_url:
        return "#", "#"
    parts = base_url.split(prefix, 1)[1].strip("/").split("/")
    if len(parts) < 2:
        return "#", "#"
    user, repo = parts[0], parts[1]
    return (
        f"https://github.com/{user}/{repo}/blob/main/daily/INDEX.md",
        f"https://github.com/{user}/{repo}",
    )


def _write_archive(
    path: Path, date_str: str, theme: str, items: list[dict], pushed: bool
) -> None:
    """原子写归档；pushed 用于当日幂等保护"""
    archive = {
        "date": date_str,
        "theme": theme,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "pushed": pushed,
        "items": items,
    }
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def run(config_path: str = "config.yaml") -> int:
    cfg = load_config(config_path)
    dry_run = cfg.get("debug", {}).get("dry_run", False)
    date_str = today_str()
    theme = _pick_theme(date_str)

    print(f"\n========== 每日审美推送 · {date_str} ==========")
    print(f"主题：{theme}")
    print(f"模式：{'DRY-RUN' if dry_run else '正式推送'}\n")

    output_dir = ROOT / cfg.get("repo", {}).get("output_dir", "daily")
    images_dir = ensure_dir(output_dir / date_str)
    archive_path = images_dir / "index.json"

    # 当日幂等：正式模式下今天已推送过就跳过，避免手动重跑重复发信
    if archive_path.exists() and not dry_run:
        try:
            prev = json.loads(archive_path.read_text(encoding="utf-8"))
            if prev.get("pushed"):
                print("[main] 今日已推送，跳过（幂等保护）")
                return 0
        except Exception as exc:
            print(f"[main] 读取历史归档失败，按未推送处理: {exc}")

    # 1. 抓图
    artworks = pick_artworks(cfg, cfg.get("schedule", {}).get("total_cards", 4))
    if not artworks:
        print("[main] 没抓到任何作品，退出")
        return 1

    # 2. 归档下载：Met / NASA 落盘，Unsplash 只热链
    print(f"[main] 归档目录 {images_dir}")
    ready_artworks: list[Artwork] = []
    for aw in artworks:
        if aw.source == "met":
            aw = met_museum.download(aw, images_dir)
        elif aw.source == "unsplash":
            aw = unsplash.download(aw, images_dir)
        elif aw.source == "nasa":
            aw = nasa_apod.download(aw, images_dir)

        if aw.extra.get("delivery") == "hotlink":
            # Unsplash API Guidelines：只热链，没有本地文件，但仍是有效作品
            ready_artworks.append(aw)
            print(f"[main] {aw.source}:{aw.source_id} 使用官方热链，不落盘")
        elif aw.local_path:
            ready_artworks.append(aw)
        else:
            print(f"[main] {aw.source}:{aw.source_id} 下载失败，跳过")
    if not ready_artworks:
        print("[main] 所有图片都不可用")
        return 1

    # 3. AI 生成讲解
    print(f"\n[main] 为 {len(ready_artworks)} 张作品生成讲解")
    llm_cfg = cfg.get("llm", {})
    commentaries = generate_batch(
        artworks=[asdict(a) for a in ready_artworks],
        api_key=llm_cfg.get("api_key", ""),
        base_url=llm_cfg.get("base_url", "https://api.deepseek.com/v1"),
        model=llm_cfg.get("model", "deepseek-chat"),
    )
    items = []
    for aw, comm in zip(ready_artworks, commentaries):
        items.append({"artwork": asdict(aw), "commentary": comm, "cid": f"img_{aw.stable_key()}"})
        print(f"  · [{aw.source}] {aw.title[:30]}... 已生成")

    # 4. 先落归档：推送失败也不会丢当天记录
    _write_archive(archive_path, date_str, theme, items, pushed=False)
    print(f"[main] 归档已写入 {archive_path}")

    # 5. 推送（图片一律走图源官方直链，不依赖仓库 commit / CDN）
    if dry_run:
        print("\n[main] DRY-RUN：跳过邮件与微信推送")
    else:
        archive_url, project_url = _repo_urls(cfg.get("repo", {}).get("base_url", ""))

        if cfg.get("email", {}).get("enabled", True):
            print("\n[main] 推送邮件")
            ok = send_email(
                artworks_with_commentary=items,
                date_str=date_str,
                theme=theme,
                smtp_config=cfg.get("email", {}),
                archive_url=archive_url,
                project_url=project_url,
            )
            print(f"[main] 邮件结果: {'OK' if ok else 'FAIL'}")

        if cfg.get("wechat", {}).get("channel"):
            print("\n[main] 推送微信")
            title, md_content = build_wechat_markdown(
                items, date_str=date_str, theme=theme,
            )
            plain_text = "\n\n".join(
                f"[{it['artwork'].get('style','')}] {it['artwork'].get('title','')}\n{it['commentary']}"
                for it in items
            )
            ok = send_wechat(
                channel=cfg["wechat"]["channel"],
                config=cfg["wechat"],
                title=title,
                content=plain_text,
                markdown_for_wecom=md_content,
            )
            print(f"[main] 微信结果: {'OK' if ok else 'FAIL'}")

        _write_archive(archive_path, date_str, theme, items, pushed=True)

    # 6. 更新 INDEX.md（最近 7 天）
    _update_index(output_dir, date_str, theme, len(items))

    print("\n[main] ✅ 全部完成")
    return 0


def _pick_theme(date_str: str) -> str:
    """根据日期选一个主题（轮换 7 天）"""
    themes = [
        "今日看构图：注意画面元素的『视觉重量』与『留白节奏』。",
        "今日看色彩：留意色温冷暖的对比，以及你第一眼被什么颜色吸引。",
        "今日看光影：想象光源方向，思考艺术家如何『用暗托亮』。",
        "今日看质感：试试观察『笔触』『材质』『颗粒感』。",
        "今日看情绪：闭上眼回想这张图，它让你感到什么？",
        "今日看细节：找一处容易被忽略的角落，那里藏着作者的签名。",
        "今日看历史：了解一下作品的创作年代与同时代发生了什么。",
    ]
    try:
        weekday = datetime.strptime(date_str, "%Y-%m-%d").weekday()
        return themes[weekday]
    except Exception:
        return themes[0]


def _update_index(output_dir: Path, today: str, theme: str, count: int) -> None:
    """在 daily/ 根目录写一个 INDEX.md 记录最近 7 天"""
    index_path = output_dir / "INDEX.md"
    line = f"- **{today}** · {theme}（{count} 张）"
    history: list[str] = []
    if index_path.exists():
        content = index_path.read_text(encoding="utf-8")
        # 提取已有行，并去掉同一天的旧记录（当日重跑不产生重复行）
        history = [
            l for l in content.splitlines()
            if l.startswith("- ") and not l.startswith(f"- **{today}**")
        ]
    history.insert(0, line)
    history = history[:7]
    body = "# 每日审美日课 · 最近 7 天\n\n" + "\n".join(history) + "\n"
    index_path.write_text(body, encoding="utf-8")


# ============ CLI ============

def main() -> None:
    parser = argparse.ArgumentParser(description="每日审美推送")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    parser.add_argument("--dry-run", action="store_true", help="只生成文件，不推送")
    args = parser.parse_args()

    # 命令行 --dry-run 强制覆盖
    if args.dry_run:
        os.environ["DRY_RUN"] = "true"

    sys.exit(run(args.config))


if __name__ == "__main__":
    main()
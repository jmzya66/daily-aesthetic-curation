# 🎨 每日审美推送 · Daily Aesthetic Curation

> 每天给手机送一组精选图 + 一段观察笔记，留两分钟看张好图。

每天早上 8:17（北京时间）系统从三个免费高质量图源抽取 3-5 张不同风格的作品（古典艺术 / 摄影 / 天文），配一段中文观察笔记，通过**邮件 + 微信**双通道推送到手机。

**讲解默认不接 LLM**：`ai_commentary.py` 用「当日审美维度 + 作品元数据」离线拼装观察笔记（一句可验证的事实 + 一个可操作的观察动作），零依赖、每张不同。7 个维度共 28 条引导句在 `OBSERVATION_LINES` 里维护；同一天的卡片按轮转分配不同句子（每维度 4 条，超过 4 张才循环）。只有显式配置 `LLM_API_KEY` 才改走原来的 OpenAI 兼容接口。

图片一律使用图源官方直链：Unsplash 按 API Guidelines 只热链、不转存，Met / NASA 为公共领域作品。仓库 `daily/` 目录只用于历史回溯，不参与图片投递，因此邮件送达不依赖 commit 或 CDN 缓存。

整套系统基于 **GitHub Actions** 免费运行，**零服务器成本**。仓库需设为**公开**。

> 定时任务已恢复：每天 UTC 0:17（北京时间 8:17）自动推送，避开 UTC 整点高峰。GitHub 对定时任务没有准点 SLA，仍可能延迟。手动触发（Actions → Run workflow）可用于验证或补跑。归档日期按北京时间计算。

---

## ✨ 特性

- 🖼️ **多图源组合**：Met Museum（古典艺术 CC0）+ Unsplash（全球摄影）+ NASA APOD（每日天文图）
- 🎲 **风格多样性**：每天 3-5 张卡片，横跨油画、摄影、天文、设计等不同维度
- 📝 **离线观察笔记**：按当日审美维度 + 作品元数据拼装，每张不同；不接 LLM、零依赖，LLM 分支可选
- 📧 **精美邮件**：响应式 HTML 邮件模板，移动端友好
- 💬 **微信双通道**：支持 Server酱（5 条/天）和企业微信自建应用（无限）
- 📚 **历史归档**：Met / NASA 图片与全部讲解自动提交到 GitHub 仓库；Unsplash 只留官方链接
- 💰 **完全免费**：依赖 GitHub Actions（每月 2000 分钟免费额度）+ 各项 API 免费层
- 🔧 **零服务器**：GitHub Actions 即调度器，不需要任何云服务器

---

## 🏗 架构

```
┌─────────────────────┐
│  GitHub Actions     │  每天 UTC 0:17 (北京时间 8:17)
│  (调度中心)          │
└──────────┬──────────┘
           │
   ┌───────┴────────┐
   ▼                ▼
【抓图】          【观察笔记】
Met Museum       事实句 + 当日维度引导句
Unsplash         7 维度 × 4 条语料池
NASA APOD        （LLM 为可选分支，默认不接）
   │
   ▼
【邮件】     【微信】
SMTP 推送   企业微信 / Server酱
QQ/Gmail    Markdown + 图片
   │
   ▼
【归档】git commit 到仓库 daily/YYYY-MM-DD/
        ↓ 仅供历史回溯
       推送图片不走 CDN，邮件可点击「查看历史日课」
```

---

## 🚀 5 分钟快速开始

### 1. Fork 或创建新仓库

把这个项目推到你的 GitHub 账号下，**仓库必须设为公开**（历史归档页与项目源码链接指向 GitHub 页面）。

### 2. 准备 API Keys

| 服务             | 用途       | 注册地址                                                       | 免费额度         |
| -------------- | -------- | ---------------------------------------------------------- | ------------ |
| **Unsplash**   | 摄影图源     | [unsplash.com/developers](https://unsplash.com/developers) | demo 50 次/小时；生产 1000 次/小时 |
| **NASA**       | 天文图源     | [science.nasa.gov](https://science.nasa.gov/)              | 公开 feed 免 key，一次取最近约 25 条 |
| **Met Museum** | 古典艺术     | 无需 key（CC0）                                                | 80 次/秒       |
| **QQ 邮箱**      | SMTP 推送  | 已有 QQ 即可                                                   | —              |
| **Server酱**    | 微信推送     | [sct.ftqq.com](https://sct.ftqq.com)                       | 5 条/天        |
| **企业微信**       | 微信推送     | [work.weixin.qq.com](https://work.weixin.qq.com)           | 无限制          |
| **LLM（可选）**  | 讲解生成   | 任意 OpenAI 兼容服务                                          | **当前默认不接** |

> 💡 **推荐组合**：Unsplash + NASA + QQ邮箱 + Server酱（或企业微信），**不需要任何 LLM 服务，也不需要 NASA API key**。
> Unsplash 图片按 [API Guidelines](https://help.unsplash.com/en/articles/2511245-unsplash-api-guidelines) 只热链官方 URL，不下载转存；请勿把图片搬到自己的 CDN。
> NASA 已切到免 key 的公开 feed `science.nasa.gov/wp-json/wp/v2/-basic`；旧端点 `api.nasa.gov/planetary/` 计划 2026-12 下线。

### 3. 配置 GitHub Secrets

进入仓库 `Settings` → `Secrets and variables` → `Actions` → `New repository secret`，添加以下项：

#### 必须配置（当前不接 LLM，无需任何 AI 服务密钥）

```
UNSPLASH_ACCESS_KEY      # Unsplash Access Key
EMAIL_USERNAME           # 发件 QQ 邮箱，如 12345@qq.com
EMAIL_PASSWORD           # QQ 邮箱授权码（不是登录密码）
EMAIL_TO                 # 收件邮箱，可以多个；自己发给自己可填同一个
REPO_BASE_URL            # https://raw.githubusercontent.com/jmzya66/daily-aesthetic-curation/main
```
`REPO_BASE_URL` 只用于推导历史归档页与项目源码链接，不用于图片投递。
`EMAIL_USERNAME` 是发件账号、`EMAIL_TO` 是收件地址，两者不是同一个字段，但个人自用可填同一个邮箱。

可选：`LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`（仅在启用 LLM 分支时需要；NASA 已免 key）、`EMAIL_SMTP_HOST`（默认 smtp.qq.com）、`EMAIL_SMTP_PORT`（默认 465）、`WECHAT_CHANNEL`（不配则按凭据自动推断）、`TOTAL_CARDS`（默认 4）。

#### 微信通道二选一

**A. Server酱**（简单，5 条/天）

```
WECHAT_SENDKEY           # Server酱 SendKey
```

**B. 企业微信自建应用**（推荐，无次数限制）

```
WECOM_CORPID             # 企业 ID
WECOM_AGENTID            # 应用 ID
WECOM_CORPSECRET         # 应用 Secret
```

企业微信配置步骤：注册企业 → 「应用管理」→ 自建 → 拿到三个参数 → 「我的企业」→ 微信插件 → 扫码关注

### 4. 配置文件（本地开发才需要）

GitHub Actions 不需要 `config.yaml`（它被 `.gitignore` 排除），所有配置通过上一步的 Secrets 注入，代码内已有默认值。本地试运行时才把 `config.example.yaml` 复制为 `config.yaml`。

### 5. 触发首次运行

前置条件：`.github/workflows/daily.yml` 必须已在仓库里，Actions 才会出现 `Daily Aesthetic Curation`。网页批量上传时以点开头的目录容易被跳过，若左侧没有这个工作流，用 `Add file → Create new file`、文件名填 `.github/workflows/daily.yml` 手动补上。

进入仓库的 `Actions` 标签 → 选择 `Daily Aesthetic Curation` → `Run workflow` → 选 `dry_run=true` 先试一次。

成功后想真正推送，把 `dry_run` 改为 `false`。注意：若当天定时任务已跑过（归档 `daily/YYYY-MM-DD/index.json` 的 `pushed` 为 `true`），正式运行会被当日幂等直接跳过；需先在仓库里把该字段改为 `false` 再手动跑，或等第二天自动运行。

---

## 📁 项目结构

```
daily-aesthetic-curation/
├── .github/workflows/
│   └── daily.yml             # GitHub Actions 工作流（每天 8:17）
├── src/
│   ├── __init__.py
│   ├── main.py               # 主流程入口
│   ├── models.py             # 共享数据结构
│   ├── ai_commentary.py      # 离线观察笔记（7 维度语料池），LLM 分支可选
│   ├── fetchers/
│   │   ├── met_museum.py     # 古典艺术
│   │   ├── unsplash.py       # 摄影
│   │   └── nasa_apod.py      # 天文
│   └── pushers/
│       ├── email_sender.py   # 邮件
│       └── wechat_sender.py  # 微信
├── templates/
│   └── email.html.j2         # 邮件 HTML 模板
├── config.example.yaml       # 配置示例
├── .env.example              # 本地开发环境变量
├── requirements.txt
└── README.md
```

运行时会在根目录生成 `daily/YYYY-MM-DD/` 目录，里面是 Met / NASA 的归档图片和 `index.json`；Unsplash 只存官方链接、不落盘。

---

## 🔧 详细配置

### 修改每日推送时间

编辑 `.github/workflows/daily.yml` 的 cron 表达式（UTC 时间）：

```yaml
schedule:
  - cron: "17 0 * * *"   # 北京时间 8:17（当前值）
  # - cron: "30 22 * * *"  # 北京时间 6:30
  # - cron: "0 1 * * *"   # 北京时间 9:00
```

工具：[crontab.guru](https://crontab.guru)

> 建议避开 `:00` / `:30` 整点：UTC 0:00 是全网 daily 任务最拥挤的时刻，2026-11-09 曾排队到北京 12:51 才触发。改分钟只降低延迟概率，GitHub 不保证准点。

### 调整每日卡片数量

编辑 `config.yaml`：

```yaml
schedule:
  total_cards: 4   # 改成 3-7 都可以
  min_cards: 3     # 少于这个数就不推送，避免发出残缺内容
```

`min_cards` 是防静默降级的闸门：某个图源挂掉时，正式运行会写完归档后**跳过推送并让 Actions 失败**（你能收到失败通知），dry-run 只打印告警方便排查。也可用环境变量 `MIN_CARDS` 覆盖。

图源现状：Met Museum 的 `/search` 端点已返回 410，项目改用 `/objects` 全量 ID 池抽样 + 并发请求详情；NASA 用免 key 的 `science.nasa.gov` feed，且只取 `hdurl`（feed 的 `url` 字段是 HTML 页面，不是图片）。

### 调整观察笔记

离线讲解的语料在 `src/ai_commentary.py` 的 `OBSERVATION_LINES`：按构图 / 色彩 / 光影 / 质感 / 情绪 / 细节 / 历史 7 个维度各存 4 条可操作的观察动作，改这里就能换每日提示。`generate_batch()` 会让同一批卡片轮转拿到不同句子，起点由当日主题决定。`_fact_sentence()` 负责从各图源元数据拼事实句。

`SYSTEM_PROMPT` / `USER_PROMPT_TEMPLATE` 只在启用 LLM 分支（配置 `LLM_API_KEY`）时生效。

### 修改每日主题文案

编辑 `src/main.py` 的 `_pick_theme()` 函数，决定每周 7 天分别推送什么审美维度。

### 增加新的图源

1. 在 `src/fetchers/` 新建 `xxx.py`，实现 `fetch()` 和 `download()` 两个函数
2. 返回标准的 `Artwork` 对象
3. 在 `src/main.py` 的 `pick_artworks()` 里加一个分支
4. 在 `src/pushers/email_sender.py` 的 `SOURCE_LABELS` 加一个来源说明

---

## 🛠 本地开发

```bash
# 1. 克隆仓库
git clone https://github.com/jmzya66/daily-aesthetic-curation.git
cd daily-aesthetic-curation

# 2. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 复制配置
cp config.example.yaml config.yaml
cp .env.example .env
# 然后编辑 .env 填入真实 key

# 5. 试运行（dry-run 不会真的发邮件/微信）
python src/main.py --dry-run

# 6. 正式运行
python src/main.py
```

---

## ❓ Troubleshooting

### Q: GitHub Actions 跑失败了？

打开 `Actions` → 选中失败的那次运行 → 查看日志。常见问题：

- Secrets 没配齐：检查 `Settings` → `Secrets`
- API key 无效：到对应平台重置 key
- SMTP 认证失败：QQ 邮箱要用**授权码**不是密码
- 张数不足导致失败退出：日志里会有 `⚠️` 与图源缺席提示，对照 `[met]` / `[nasa]` / `[unsplash]` 的告警定位；常见原因是 Met 的 `/objects` 抽样没命中、或 NASA 图片下载被拒
- 某个推送通道失败：Actions 的 Annotations 会出现红色 `::error::` 提示，归档 `index.json` 的 `push_results` 记录每个通道的真实结果。job 仍判成功以保证当天归档被 commit，**别只看绿色就以为都送达了**

### Q: 邮件被识别为垃圾邮件？

- 用 QQ 邮箱发到自己的 QQ 邮箱一般不会
- 如果发到 Gmail，可以加 SPF/DKIM 记录，或者改用 Resend 这类专业服务

### Q: 微信收不到？

**Server酱**：

- 免费版每天 5 条，超额会失败
- 检查是否关注了「方糖」公众号

**企业微信**：

- 手机上必须下载企业微信 App（即使你不打算用）
- 在企业微信「设置」→「新消息通知」关闭「仅在企业微信中接收消息」才能在微信里收到

### Q: 想换其他 LLM？（仅启用 LLM 分支时适用，当前默认不接）

修改 `config.yaml`：

```yaml
llm:
  api_key: "sk-xxxx"
  base_url: "https://api.openai.com/v1"   # OpenAI
  # base_url: "https://api.moonshot.cn/v1"   # 月之暗面
  # base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"  # 阿里通义
  model: "gpt-4o-mini"
```

只要是 OpenAI 兼容接口都行。

### Q: 图片在邮件里加载很慢？

邮件直接使用图源官方地址（Unsplash `images.unsplash.com`、Met `images.metmuseum.org`、NASA `assets.science.nasa.gov`），不再经过 jsDelivr。国内访问 Met / NASA 可能偏慢，这是「合规优先」的代价；若明显影响体验，可考虑把这两个公共领域图源改为压缩后自建托管（Unsplash 仍不能转存）。

### Q: 想看历史日课？

每次运行都会把 Met / NASA 的图片和 `index.json` commit 到 `daily/YYYY-MM-DD/`，`daily/INDEX.md` 记录最近 7 天；邮件底部「查看历史日课」指向该索引页。Unsplash 只存官方 URL，若原图被作者删除，历史里这张会显示不出来。

---

## 🎯 扩展想法

- [ ] 增加 **Pixabay**（插画）和 **ColourLovers**（配色）作为更多风格
- [ ] 每周日推送"本周精选 Top 5"
- [ ] 支持自定义关键词黑名单（屏蔽某些风格）
- [ ] 用 AI 把每张图生成配套的中文短诗
- [ ] 增加「不感兴趣」反馈按钮（基于 Notion 数据库 + Webhook）

---

## 📜 License

MIT

---

## 🙏 Credits

图源：

- [The Metropolitan Museum of Art Open Access](https://www.metmuseum.org/about-the-met/policies-and-documents/open-access) (CC0)
- [Unsplash](https://unsplash.com) — 本项目通过 API 取图，除 Unsplash License 外还须遵守 [API Guidelines](https://help.unsplash.com/en/articles/2511245-unsplash-api-guidelines)：只热链 `photo.urls`、署名 Unsplash 与摄影师、回链带 utm
- [NASA APOD](https://apod.nasa.gov) (Public Domain)

工具：

- [GitHub Actions](https://github.com/features/actions)
- [Jinja2](https://jinja.palletsprojects.com)
- LLM（DeepSeek / OpenAI 等）为可选分支，当前未启用

灵感：来自「每天留两分钟给一张好图」的想法。

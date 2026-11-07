# 🎨 每日审美推送 · Daily Aesthetic Curation

> 每天给手机送一组精选图 + 一段 AI 审美笔记，留两分钟看张好图。

每天早上 8 点（北京时间），系统自动从三个免费高质量图源中抽取 3-5 张不同风格的作品（古典艺术 / 摄影 / 天文），调用 LLM 生成一段 50-80 字的中文审美讲解，然后通过**邮件 + 微信**双通道推送到你手机上。

图片一律使用图源官方直链：Unsplash 按 API Guidelines 只热链、不转存，Met / NASA 为公共领域作品。仓库 `daily/` 目录只用于历史回溯，不参与图片投递，因此邮件送达不依赖 commit 或 CDN 缓存。

整套系统基于 **GitHub Actions** 免费运行，**零服务器成本**。仓库需设为**公开**。

> 当前 `schedule` 已注释停用，避免 Secrets 未配置时每天空跑留下无效归档。填好 Secrets 后按下方「修改每日推送时间」一节取消注释即可恢复每天 8:00 自动推送；手动触发（Actions → Run workflow）不受影响。

---

## ✨ 特性

- 🖼️ **多图源组合**：Met Museum（古典艺术 CC0）+ Unsplash（全球摄影）+ NASA APOD（每日天文图）
- 🎲 **风格多样性**：每天 3-5 张卡片，横跨油画、摄影、天文、设计等不同维度
- 🤖 **AI 审美讲解**：调用 DeepSeek / GPT-4o-mini 等 LLM，生成有质感的中文审美笔记（50-80 字）
- 📧 **精美邮件**：响应式 HTML 邮件模板，移动端友好
- 💬 **微信双通道**：支持 Server酱（5 条/天）和企业微信自建应用（无限）
- 📚 **历史归档**：Met / NASA 图片与全部讲解自动提交到 GitHub 仓库；Unsplash 只留官方链接
- 💰 **完全免费**：依赖 GitHub Actions（每月 2000 分钟免费额度）+ 各项 API 免费层
- 🔧 **零服务器**：GitHub Actions 即调度器，不需要任何云服务器

---

## 🏗 架构

```
┌─────────────────────┐
│  GitHub Actions     │  每天 UTC 0:00 (北京时间 8:00)
│  (调度中心)          │
└──────────┬──────────┘
           │
   ┌───────┴────────┐
   ▼                ▼
【抓图】          【AI 讲解】
Met Museum       DeepSeek / GPT
Unsplash          输入元数据 → 50-80 字讲解
NASA APOD
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
| **DeepSeek**   | AI 审美讲解  | [platform.deepseek.com](https://platform.deepseek.com)     | 按平台实际计费为准 |
| **Unsplash**   | 摄影图源     | [unsplash.com/developers](https://unsplash.com/developers) | demo 50 次/小时；生产 1000 次/小时 |
| **NASA**       | 天文图源     | [api.nasa.gov](https://api.nasa.gov)                       | DEMO_KEY 30 次/小时；自有 key 1000 次/小时 |
| **Met Museum** | 古典艺术     | 无需 key（CC0）                                                | 80 次/秒       |
| **QQ 邮箱**      | SMTP 推送  | 已有 QQ 即可                                                   | 无限制          |
| **Server酱**    | 微信推送     | [sct.ftqq.com](https://sct.ftqq.com)                       | 5 条/天        |
| **企业微信**       | 微信推送（推荐） | [work.weixin.qq.com](https://work.weixin.qq.com)           | 无限制          |

> 💡 **推荐组合**：DeepSeek + Unsplash + NASA + QQ邮箱 + 企业微信。
> Unsplash 图片按 [API Guidelines](https://help.unsplash.com/en/articles/2511245-unsplash-api-guidelines) 只热链官方 URL，不下载转存；请勿把图片搬到自己的 CDN。

### 3. 配置 GitHub Secrets

进入仓库 `Settings` → `Secrets and variables` → `Actions` → `New repository secret`，添加以下项：

#### 必须配置

```
LLM_API_KEY              # DeepSeek 或 OpenAI 的 API key
UNSPLASH_ACCESS_KEY      # Unsplash Access Key
NASA_API_KEY             # 建议配自有 key，否则回落 DEMO_KEY（30 次/小时，易限流）
EMAIL_USERNAME           # 你的 QQ 邮箱，如 12345@qq.com
EMAIL_PASSWORD           # QQ邮箱授权码（不是登录密码）
EMAIL_TO                 # 接收邮件的邮箱（可以多个，逗号分隔）
REPO_BASE_URL            # https://raw.githubusercontent.com/你的用户名/你的仓库/main
                         # 只用于推导历史归档页与项目源码链接，不用于图片投递
```

可选：`LLM_BASE_URL` / `LLM_MODEL`、`EMAIL_SMTP_HOST`（默认 smtp.qq.com）、`EMAIL_SMTP_PORT`（默认 465）、`WECHAT_CHANNEL`（不配则按凭据自动推断）、`TOTAL_CARDS`（默认 4）。

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

进入仓库的 `Actions` 标签 → 选择 `Daily Aesthetic Curation` → `Run workflow` → 选 `dry_run=true` 先试一次。

成功后改成 `dry_run=false` 真正推送。

---

## 📁 项目结构

```
daily-aesthetic-curation/
├── .github/workflows/
│   └── daily.yml             # GitHub Actions 定时任务
├── src/
│   ├── __init__.py
│   ├── main.py               # 主流程入口
│   ├── models.py             # 共享数据结构
│   ├── ai_commentary.py      # LLM 讲解生成
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

运行时会在根目录生成 `daily/YYYY-MM-DD/` 目录，里面是当天下载的图片和 `index.json`。

---

## 🔧 详细配置

### 修改每日推送时间

编辑 `.github/workflows/daily.yml` 的 cron 表达式（UTC 时间）：

```yaml
schedule:
  - cron: "0 0 * * *"   # 北京时间 8:00
  # - cron: "30 22 * * *"  # 北京时间 6:30
  # - cron: "0 1 * * *"   # 北京时间 9:00
```

工具：[crontab.guru](https://crontab.guru)

### 调整每日卡片数量

编辑 `config.yaml`：

```yaml
schedule:
  total_cards: 4   # 改成 3-7 都可以
```

### 自定义讲解 prompt

编辑 `src/ai_commentary.py` 的 `SYSTEM_PROMPT` 和 `USER_PROMPT_TEMPLATE`。

比如想强调"色彩"维度，就改 prompt。

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
git clone https://github.com/your_username/daily-aesthetic-curation.git
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

### Q: 想换其他 LLM？

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

邮件直接使用图源官方地址（Unsplash `images.unsplash.com`、Met `images.metmuseum.org`、NASA `apod.nasa.gov`），不再经过 jsDelivr。国内访问 Met / NASA 可能偏慢，这是「合规优先」的代价；若明显影响体验，可考虑把这两个公共领域图源改为压缩后自建托管（Unsplash 仍不能转存）。

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

- [DeepSeek](https://deepseek.com) / [OpenAI](https://openai.com)
- [GitHub Actions](https://github.com/features/actions)
- [Jinja2](https://jinja.palletsprojects.com)

灵感：来自对"日常审美训练"的执念。

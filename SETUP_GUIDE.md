# 🚀 HSE资讯自动化抓取系统 - 完整部署指南

> 版本：V1.0  
> 更新日期：2026年1月19日

---

## 📋 系统概述

本系统自动执行以下任务：
1. **每日抓取**：从今日头条抓取"施工管理"、"安全管理"、"环境保护管理"相关资讯
2. **AI筛选**：使用 Gemini 2.5 Pro 智能筛选 Top 20 专业文章
3. **邮件推送**：每天北京时间早上 9:00 发送精选资讯到指定邮箱

---

## 第一阶段：获取必要的API密钥

### 1.1 获取 Gemini API Key

1. 访问 [Google AI Studio](https://aistudio.google.com/apikey)
2. 登录您的 Google 账户
3. 点击左侧菜单的 **"Get API key"** 或直接访问 API Keys 页面
4. 点击 **"Create API key"** 按钮
5. 选择或创建一个 Google Cloud 项目
6. 复制生成的 API Key（格式类似：`AIzaSy...`）

> ⚠️ **重要**：妥善保存此密钥，不要公开分享

### 1.2 获取 Gmail 应用专用密码

需要为 Gmail SMTP 创建应用密码：

1. 访问 [Google 应用密码设置](https://myaccount.google.com/apppasswords)
2. 登录您的 Google 账户
3. 选择应用类型为 **"邮件"**，设备为 **"其他"**
4. 输入名称（如：`HSE-News-Bot`）
5. 点击 **"生成"**
6. 复制16位应用密码（格式：`xxxx xxxx xxxx xxxx`）

> **注意**：需要先开启两步验证才能生成应用密码

---

## 第二阶段：创建 GitHub 仓库

### 2.1 创建新仓库

1. 访问 https://github.com/new
2. 仓库名称：`hse-news-automation`（或您喜欢的名称）
3. 选择 **Private**（私有仓库，保护API密钥）
4. 点击 **"Create repository"**

### 2.2 上传项目文件

将本地 `HSE-资讯自动化系统` 文件夹中的所有文件上传到仓库：

```
HSE-资讯自动化系统/
├── .github/workflows/daily_news.yml    # GitHub Actions 工作流
├── fetch_news.py                        # 主Python脚本
├── fetch_news.sh                        # Bash备用脚本
├── send_email.py                        # 邮件发送模块
├── requirements.txt                     # Python依赖
├── .env.example                         # 环境变量示例
├── .gitignore                           # Git忽略规则
└── README.md                            # 项目说明
```

### 2.3 配置 GitHub Secrets（关键步骤）

1. 进入仓库页面 → **Settings** → **Secrets and variables** → **Actions**
2. 点击 **"New repository secret"**，添加以下3个密钥：

| Secret 名称 | 值 | 说明 |
|------------|-----|------|
| `GEMINI_API_KEY` | `AIzaSy...` | 在1.1获取的API Key |
| `MAIL_USERNAME` | `yourname@gmail.com` | 您的Gmail地址 |
| `MAIL_PASSWORD` | `xxxx xxxx xxxx xxxx` | 在1.2获取的16位应用密码 |

---

## 第三阶段：本地测试（可选）

如果想在本地先测试系统功能：

```bash
# 1. 进入项目目录
cd HSE-资讯自动化系统

# 2. 安装依赖
pip install -r requirements.txt

# 3. 创建 .env 文件（复制示例）
cp .env.example .env

# 4. 编辑 .env 文件，填入您的密钥
# GEMINI_API_KEY=您的Key
# MAIL_USERNAME=您的邮箱
# MAIL_PASSWORD=您的应用密码
# MAIL_RECEIVER=接收邮件的邮箱

# 5. 测试运行（只抓取不发邮件）
python fetch_news.py --fetch-only

# 6. 完整测试（包含邮件发送）
python fetch_news.py
```

---

## 第四阶段：启用自动化并验证

### 4.1 启用 GitHub Actions

1. 进入仓库 → **Actions** 标签页
2. 如果提示启用，点击 **"I understand my workflows, go ahead and enable them"**

### 4.2 手动触发测试

1. 在 Actions 页面，点击左侧 **"Daily HSE News"** 工作流
2. 点击右侧 **"Run workflow"** 按钮
3. 选择 `main` 分支，点击 **"Run workflow"**

### 4.3 验证结果

- 等待几分钟，查看工作流执行结果（绿色✓表示成功）
- 检查您的 Gmail 收件箱是否收到 HSE 资讯邮件
- 如有报错，查看 Actions 日志排查问题

---

## 📅 自动运行时间配置

系统默认配置为每天 **北京时间早上 9:00** 自动运行：

```yaml
# .github/workflows/daily_news.yml
on:
  schedule:
    - cron: '0 1 * * *'  # UTC时间凌晨1点 = 北京时间早上9点
```

### 修改运行时间

如需修改，编辑 `cron` 表达式：

| 北京时间 | UTC时间 | Cron表达式 |
|---------|---------|-----------|
| 07:00 | 23:00(前一天) | `0 23 * * *` |
| 08:00 | 00:00 | `0 0 * * *` |
| 09:00 | 01:00 | `0 1 * * *` |
| 12:00 | 04:00 | `0 4 * * *` |
| 18:00 | 10:00 | `0 10 * * *` |

---

## 🔧 常见问题排查

### 邮件发送失败

| 错误类型 | 可能原因 | 解决方案 |
|---------|---------|---------|
| 认证失败 | Gmail应用密码错误 | 重新生成应用密码，确保复制完整 |
| 连接被拒 | 未开启两步验证 | 开启Google账户两步验证 |
| 发送超时 | 网络问题 | 检查网络，稍后重试 |

### API调用失败

| 错误类型 | 可能原因 | 解决方案 |
|---------|---------|---------|
| 401 Unauthorized | API Key无效 | 检查密钥是否正确复制 |
| 429 Too Many Requests | 超过配额 | 等待配额重置或升级计划 |
| 500 Internal Error | 服务端错误 | 系统会自动重试 |

### 抓取无结果

| 错误类型 | 可能原因 | 解决方案 |
|---------|---------|---------|
| RSS获取失败 | RSSHub临时不可用 | 系统会自动尝试备用镜像 |
| 无新闻 | 24小时内无相关新闻 | 正常情况，等待次日 |
| 解析失败 | RSS格式变化 | 检查日志，更新解析逻辑 |

### GitHub Actions未运行

| 错误类型 | 可能原因 | 解决方案 |
|---------|---------|---------|
| 工作流禁用 | 新仓库默认禁用 | 在Actions页面手动启用 |
| 私有仓库限制 | 超过免费额度 | 检查Actions使用量 |
| 语法错误 | YAML格式错误 | 使用在线YAML验证器检查 |

---

## 📊 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions (定时触发)                  │
│                     每天 UTC 01:00 运行                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      fetch_news.py                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ RSSFetcher  │→ │GeminiFilter │→ │  ReportGenerator    │  │
│  │ (数据抓取)   │  │ (AI筛选)    │  │  (报告生成)         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
        │                   │                    │
        ▼                   ▼                    ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────────────┐
│    RSSHub     │  │ Gemini 2.5    │  │   Gmail SMTP          │
│  (今日头条)    │  │ Pro API       │  │   (邮件发送)          │
└───────────────┘  └───────────────┘  └───────────────────────┘
```

---

## 🔗 相关链接

- [Google AI Studio](https://aistudio.google.com/) - 获取Gemini API Key
- [Google 账户安全](https://myaccount.google.com/security) - 开启两步验证
- [Google 应用密码](https://myaccount.google.com/apppasswords) - 生成应用密码
- [GitHub Actions 文档](https://docs.github.com/en/actions) - 工作流配置参考
- [RSSHub 文档](https://docs.rsshub.app/) - RSS源配置参考

---

## 📝 更新日志

### V1.0 (2026-01-19)
- ✅ 初始版本发布
- ✅ 支持今日头条RSS抓取
- ✅ Gemini 2.5 Pro智能筛选
- ✅ 24小时新鲜度过滤
- ✅ 自动重试机制（tenacity）
- ✅ 专业HSE领域提示词优化
- ✅ Gmail邮件推送
- ✅ GitHub Actions自动化部署

---

> 💡 **提示**：如有问题，请检查 GitHub Actions 日志，或在项目中创建 Issue。

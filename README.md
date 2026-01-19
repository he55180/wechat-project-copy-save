# 🛡️ HSE资讯自动化抓取系统

> 每日自动检索、AI智能筛选、邮件推送安环管理热文

[![Daily News](https://github.com/YOUR_USERNAME/hse-news-automation/actions/workflows/daily_news.yml/badge.svg)](https://github.com/YOUR_USERNAME/hse-news-automation/actions/workflows/daily_news.yml)

## 📋 项目简介

本系统自动完成以下工作流程：

```
🔍 抓取 → 🤖 AI筛选 → 📧 邮件推送
```

1. **自动检索**：每日抓取今日头条上关于"施工管理"、"安全管理"、"环境保护管理"等关键词的文章
2. **智能筛选**：利用 Gemini 2.5 Pro 从检索结果中选出专业度最高的 Top 20
3. **自动送达**：每天早晨将精选报告发送至你的邮箱

## 🛠️ 技术栈

| 组件 | 技术选型 |
|------|----------|
| 自动化平台 | GitHub Actions |
| AI大模型 | Gemini 2.5 Pro (Google AI Studio) |
| 数据源 | RSSHub (今日头条搜索) |
| 脚本语言 | Python 3.11 |
| 邮件服务 | Gmail SMTP |

## 🚀 快速开始

### 第一步：Fork仓库

点击右上角 `Fork` 按钮，将本仓库复制到你的账户下。

### 第二步：配置Secrets

进入你的仓库 → `Settings` → `Secrets and variables` → `Actions`

添加以下Secrets：

| Secret名称 | 说明 | 获取方式 |
|------------|------|----------|
| `GEMINI_API_KEY` | Gemini API密钥 | [Google AI Studio](https://aistudio.google.com/apikey) |
| `MAIL_USERNAME` | Gmail地址 | 你的Gmail邮箱 |
| `MAIL_PASSWORD` | Gmail应用专用密码 | [生成应用密码](https://myaccount.google.com/apppasswords) |
| `MAIL_TO` | 接收邮箱（可选） | 默认发送给MAIL_USERNAME |

### 第三步：启用Actions

1. 进入仓库的 `Actions` 标签页
2. 点击 `I understand my workflows, go ahead and enable them`
3. 点击左侧 `📰 HSE Daily News` 工作流
4. 点击 `Run workflow` 手动测试一次

### 第四步：等待每日推送

系统将在每天 **北京时间 09:00** 自动运行。

## 📁 项目结构

```
HSE-资讯自动化系统/
├── .github/
│   └── workflows/
│       └── daily_news.yml    # GitHub Actions工作流
├── output/                   # 输出目录（自动生成）
│   ├── latest_report.md      # 最新报告
│   └── raw_data_*.json       # 原始数据
├── reports/                  # 历史报告归档
├── fetch_news.py             # Python主脚本
├── fetch_news.sh             # Bash脚本（备选）
├── send_email.py             # 邮件发送模块
├── requirements.txt          # Python依赖
├── .env.example              # 环境变量模板
└── README.md                 # 本文件
```

## ⚙️ 自定义配置

### 修改搜索关键词

编辑 `fetch_news.py` 中的 `Config` 类：

```python
@dataclass
class Config:
    keywords: List[str] = field(default_factory=lambda: [
        "施工管理",
        "安全管理", 
        "环境保护管理",
        "安全生产",
        "工程事故分析",
        "HSE管理"
    ])
```

### 修改推送时间

编辑 `.github/workflows/daily_news.yml` 中的cron表达式：

```yaml
schedule:
  - cron: '0 1 * * *'  # UTC 01:00 = 北京时间 09:00
```

Cron格式：`分 时 日 月 周`

### 手动触发

在Actions页面可以手动触发，并支持自定义参数：

- `keywords`: 自定义关键词（空格分隔）
- `top_n`: 筛选Top N篇（默认20）

## 🔧 本地开发

```bash
# 克隆仓库
git clone https://github.com/YOUR_USERNAME/hse-news-automation.git
cd hse-news-automation

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑.env填入你的API密钥

# 运行测试
python fetch_news.py --fetch-only  # 仅抓取，不调用AI
python fetch_news.py               # 完整运行
```

## 📧 Gmail应用专用密码设置

1. 访问 [Google账户安全设置](https://myaccount.google.com/security)
2. 确保已开启"两步验证"
3. 访问 [应用专用密码](https://myaccount.google.com/apppasswords)
4. 选择"邮件"和"Windows计算机"（或其他）
5. 点击"生成"，复制16位密码
6. 将此密码填入GitHub Secrets的 `MAIL_PASSWORD`

## ❓ 常见问题

### Q: RSSHub访问不稳定怎么办？

A: 脚本已内置多个镜像源自动切换。如果仍有问题，可以：
1. 部署自己的RSSHub实例
2. 在 `.env` 中配置 `RSSHUB_BASE`

### Q: Gemini API调用失败？

A: 检查以下几点：
1. API Key是否正确配置
2. 是否超出免费配额（约60次/分钟）
3. 网络是否可访问Google服务

### Q: 邮件发送失败？

A: 检查以下几点：
1. Gmail是否开启了"两步验证"
2. 是否使用了"应用专用密码"而非登录密码
3. Gmail是否开启了"允许安全性较低的应用"（不推荐）

## 📄 许可证

MIT License

## 🙏 致谢

- [RSSHub](https://github.com/DIYgod/RSSHub) - 开源RSS订阅源
- [Google AI Studio](https://aistudio.google.com/) - 免费Gemini API
- [GitHub Actions](https://github.com/features/actions) - 免费CI/CD

---

**🌟 如果这个项目对你有帮助，欢迎Star！**

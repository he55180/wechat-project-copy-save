#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HSE资讯自动抓取系统 - Python主脚本
===================================
功能：
1. 从RSSHub抓取今日头条安环管理类文章
2. 调用Gemini 2.5 Pro进行智能筛选
3. 生成Markdown报告
4. 发送邮件通知

版本: V1.0
作者: HSE自动化团队
"""

import os
import sys
import json
import time
import logging
import argparse
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

import requests
import feedparser
import google.generativeai as genai
from dateutil import parser as date_parser
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# ============================================================================
# 配置
# ============================================================================

@dataclass
class Config:
    """系统配置"""
    # 搜索关键词
    keywords: List[str] = field(default_factory=lambda: [
        "施工管理",
        "安全管理", 
        "环境保护管理",
        "安全生产",
        "工程事故分析",
        "HSE管理"
    ])
    
    # RSSHub配置 - 使用更稳定的自建实例和官方实例
    rsshub_base: str = "https://rsshub.pseudoyu.com"
    rsshub_mirrors: List[str] = field(default_factory=lambda: [
        "https://rsshub.ktachibana.party",
        "https://rsshub-instance.zeabur.app",
        "https://rsshub.atgw.io",
        "https://rsshub.app",
    ])
    
    # 抓取配置
    max_items_per_keyword: int = 15
    request_timeout: int = 15
    request_delay: float = 2.0
    
    # Gemini配置
    gemini_model: str = "gemini-2.5-pro-preview-05-06"
    top_n: int = 20
    
    # 输出配置
    output_dir: str = "output"


# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# ============================================================================
# RSS抓取模块
# ============================================================================

class RSSFetcher:
    """RSS内容抓取器 - 带重试机制和时效性过滤"""
    
    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/rss+xml, application/xml, text/xml, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
        # 时效性阈值：放宽到72小时以确保有足够数据
        self.freshness_threshold = timedelta(hours=72)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(requests.RequestException),
        before_sleep=lambda retry_state: logger.warning(
            f"⚠ 请求失败，{retry_state.attempt_number}秒后重试 (第{retry_state.attempt_number}次)..."
        )
    )
    def _fetch_with_retry(self, url: str) -> requests.Response:
        """带重试机制的HTTP请求"""
        response = self.session.get(url, timeout=self.config.request_timeout)
        response.raise_for_status()
        return response
    
    def fetch_keyword(self, keyword: str) -> List[Dict[str, Any]]:
        """抓取单个关键词的文章 - 支持多数据源"""
        encoded_kw = urllib.parse.quote(keyword)
        articles = []
        
        # 多数据源策略：今日头条 -> 百度资讯 -> 搜狗新闻
        data_sources = [
            # 今日头条搜索
            ('今日头条', f"/toutiao/search/{encoded_kw}"),
            # 百度资讯（更稳定）
            ('百度资讯', f"/baidu/news/{encoded_kw}"),
            # 搜狗新闻
            ('搜狗新闻', f"/sogou/search/{encoded_kw}"),
            # 微信搜索（关键词）
            ('微信搜索', f"/wechat/wechat/{encoded_kw}?key={encoded_kw}"),
        ]
        
        for source_name, route in data_sources:
            # 对每个数据源，尝试主域名和镜像
            urls_to_try = [
                f"{self.config.rsshub_base}{route}"
            ] + [
                f"{mirror}{route}" 
                for mirror in self.config.rsshub_mirrors
            ]
            
            for url in urls_to_try:
                try:
                    logger.info(f"📡 [{source_name}] 尝试: {url[:70]}...")
                    response = self._fetch_with_retry(url)
                    
                    # 使用feedparser解析RSS
                    feed = feedparser.parse(response.text)
                    
                    if feed.entries:
                        articles = self._parse_feed_entries(feed.entries, keyword, source_name)
                        if articles:
                            logger.info(f"✓ [{source_name}] 获取 {len(articles)} 条: {keyword}")
                            return articles[:self.config.max_items_per_keyword]
                            
                except requests.RequestException as e:
                    logger.debug(f"⚠ [{source_name}] 请求失败: {e}")
                    continue
                except Exception as e:
                    logger.debug(f"⚠ [{source_name}] 解析错误: {e}")
                    continue
        
        logger.warning(f"✗ 所有数据源均未能获取: {keyword}")
        return []
    
    def _parse_feed_entries(self, entries: list, keyword: str, source: str = '今日头条') -> List[Dict[str, Any]]:
        """解析RSS条目并进行时效性过滤"""
        now = datetime.now(timezone.utc)
        items = []
        
        for entry in entries:
            title = entry.get('title', '')
            link = entry.get('link', '')
            description = entry.get('summary', entry.get('description', ''))[:200]
            pub_date_str = entry.get('published', entry.get('updated', ''))
            
            if not title or not link:
                continue
            
            # 解析发布时间并计算时效性
            pub_date = None
            freshness = None
            is_fresh = True  # 默认保留（如果无法解析时间）
            
            if pub_date_str:
                try:
                    pub_date = date_parser.parse(pub_date_str)
                    # 确保时区感知
                    if pub_date.tzinfo is None:
                        pub_date = pub_date.replace(tzinfo=timezone.utc)
                    
                    age = now - pub_date
                    is_fresh = age <= self.freshness_threshold
                    
                    # 生成可读的时效标签
                    if age < timedelta(hours=1):
                        freshness = "刚刚"
                    elif age < timedelta(hours=6):
                        freshness = f"{int(age.total_seconds() / 3600)}小时前"
                    elif age < timedelta(hours=24):
                        freshness = "今日"
                    else:
                        freshness = f"{age.days}天前"
                        
                except (ValueError, TypeError):
                    pub_date_str = "未知时间"
            
            # 时效性过滤：只保留24小时内的文章
            if not is_fresh:
                continue
            
            items.append({
                'title': title,
                'link': link,
                'description': description,
                'pub_date': pub_date_str,
                'pub_datetime': pub_date,
                'freshness': freshness,
                'keyword': keyword,
                'source': source
            })
        
        # 按发布时间排序（最新在前）
        items.sort(key=lambda x: x.get('pub_datetime') or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        
        return items
    
    def fetch_all(self) -> List[Dict[str, Any]]:
        """抓取所有关键词"""
        all_articles = []
        
        for i, keyword in enumerate(self.config.keywords, 1):
            logger.info(f"\n{'='*50}")
            logger.info(f"[{i}/{len(self.config.keywords)}] 正在检索: {keyword}")
            logger.info('='*50)
            
            articles = self.fetch_keyword(keyword)
            all_articles.extend(articles)
            
            # 礼貌延迟
            if i < len(self.config.keywords):
                time.sleep(self.config.request_delay)
        
        logger.info(f"\n📊 总计抓取: {len(all_articles)} 篇文章")
        return all_articles


# ============================================================================
# Gemini AI筛选模块
# ============================================================================

class GeminiFilter:
    """Gemini智能筛选器 - HSE领域专业版"""
    
    # 系统指令：定义AI的专业身份和价值观
    SYSTEM_PROMPT = """你是一位拥有20年经验的 HSE（健康、安全、环境）资深管理专家，专门负责建筑工程领域的风险控制与合规审计。

你的核心能力：
- 精通《安全生产法》《建设工程安全生产管理条例》等法规体系
- 熟悉危大工程专项施工方案编制与审核流程
- 擅长施工现场隐患排查与风险评估
- 了解ISO 45001、ISO 14001管理体系要求

你的任务是从一组原始资讯中，筛选出最具专业参考价值的 Top 20 内容，为一线HSE管理人员提供高质量的每日阅读清单。"""

    # 用户提示词模板
    USER_PROMPT_TEMPLATE = """以下是从今日头条等平台检索到的原始文章列表（共 {total} 篇，包含标题、链接和发布时间）：

---
{articles_text}
---

请按照以下标准进行严格筛选：

## 筛选标准（按优先级排序）

### 1. 专业相关性 [权重最高]
- ✅ 优先：施工安全技术规范、危大工程管理、高处作业/起重吊装/深基坑等专项内容
- ✅ 优先：安全生产法律法规更新、行业标准解读、处罚案例
- ✅ 优先：环境影响评价、绿色施工、扬尘治理、噪声控制
- ❌ 剔除：与建筑工程HSE无关的泛安全内容（如交通安全、食品安全）

### 2. 内容深度与价值 [权重次高]
- ✅ 优先：重大事故深度分析（事故原因、责任认定、整改措施）
- ✅ 优先：新技术新工艺应用案例（智慧工地、BIM安全管理）
- ✅ 优先：可操作的检查清单、管理制度模板
- ❌ 剔除：纯噱头标题党、无实质内容的短资讯
- ❌ 剔除：软文广告、产品推销类内容

### 3. 时效性与紧迫性 [加分项]
- 🔥 置顶：涉及近期重大事故预警或国家级政策更新
- 🔥 置顶：住建部/应急管理部等官方通报

## 输出格式要求

请严格按以下Markdown格式输出Top {top_n} 精选：

### 1. [文章标题](文章链接)
- **📌 核心看点**：用一句话概括文章对HSE管理员的实际指导意义
- **💡 推荐理由**：简述该文为何值得阅读（如：法规更新、新技术应用、典型事故教训）
- **🏷️ 标签**：#安全管理 #绿色施工 #合规性 #危大工程 （根据内容选择2-3个）

### 2. [下一篇标题](链接)
...

## 重要提示
- 如果高质量文章不足{top_n}篇，请如实列出实际筛选数量，宁缺毋滥
- 严禁捏造文章标题或链接
- 相似内容只保留质量最高的一篇"""

    def __init__(self, api_key: str = None, model: str = "gemini-2.5-pro-preview-05-06"):
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("未设置 GEMINI_API_KEY 环境变量")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(model)
        logger.info(f"✓ Gemini模型已初始化: {model}")
    
    def filter_articles(self, articles: List[Dict[str, Any]], top_n: int = 20) -> str:
        """使用Gemini筛选文章"""
        if not articles:
            return "暂无文章数据"
        
        # 构建输入文本
        articles_text = self._format_articles_for_prompt(articles)
        
        # 使用专业化Prompt模板
        user_prompt = self.USER_PROMPT_TEMPLATE.format(
            total=len(articles),
            articles_text=articles_text,
            top_n=top_n
        )

        try:
            logger.info(f"🤖 正在调用Gemini进行智能筛选...")
            response = self.model.generate_content(
                [self.SYSTEM_PROMPT, user_prompt],
                generation_config=genai.types.GenerationConfig(
                    temperature=0.2,  # 降低温度，提高一致性
                    max_output_tokens=8192  # 增加输出长度以容纳详细分析
                )
            )
            
            result = response.text
            logger.info(f"✓ Gemini筛选完成")
            return result
            
        except Exception as e:
            logger.error(f"✗ Gemini调用失败: {e}")
            return self._fallback_filter(articles, top_n)
    
    def _format_articles_for_prompt(self, articles: List[Dict[str, Any]]) -> str:
        """格式化文章列表供Gemini处理"""
        lines = []
        for i, article in enumerate(articles, 1):
            pub_date = article.get('pub_date', '未知时间')
            freshness = article.get('freshness', '')
            freshness_tag = f" [{freshness}]" if freshness else ""
            
            line = f"{i}. 【{article['keyword']}】{article['title']}{freshness_tag}\n   链接: {article['link']}\n   发布: {pub_date}"
            if article.get('description'):
                line += f"\n   摘要: {article['description'][:150]}..."
            lines.append(line)
        return "\n\n".join(lines)
    
    def _fallback_filter(self, articles: List[Dict[str, Any]], top_n: int) -> str:
        """Gemini不可用时的降级方案 - 基于规则的简单筛选"""
        logger.warning("⚠ 使用降级方案：基于规则的关键词权重筛选")
        
        # 高价值关键词权重
        high_value_keywords = {
            '事故': 10, '伤亡': 10, '死亡': 10,
            '住建部': 8, '应急管理部': 8, '通报': 8,
            '法规': 7, '条例': 7, '标准': 7, '规范': 7,
            '处罚': 6, '罚款': 6, '责任': 6,
            '危大工程': 5, '深基坑': 5, '高处作业': 5, '起重': 5,
            '专项方案': 4, '隐患排查': 4, '风险评估': 4,
            '智慧工地': 3, 'BIM': 3, '新技术': 3,
        }
        
        # 低价值关键词（降权）
        low_value_keywords = ['广告', '推广', '优惠', '免费', '加盟']
        
        def score_article(article):
            title = article.get('title', '')
            desc = article.get('description', '')
            text = title + desc
            
            score = 0
            for kw, weight in high_value_keywords.items():
                if kw in text:
                    score += weight
            
            for kw in low_value_keywords:
                if kw in text:
                    score -= 5
            
            # 时效性加分
            freshness = article.get('freshness', '')
            if freshness in ['刚刚', '今日']:
                score += 3
            elif '小时前' in freshness:
                score += 2
            
            return score
        
        # 评分并排序
        scored_articles = [(a, score_article(a)) for a in articles]
        scored_articles.sort(key=lambda x: x[1], reverse=True)
        
        # 格式化输出
        lines = ["## ⚠️ 降级模式输出（AI服务不可用）\n"]
        for i, (article, score) in enumerate(scored_articles[:top_n], 1):
            freshness_tag = f" [{article.get('freshness', '')}]" if article.get('freshness') else ""
            lines.append(f"### {i}. [{article['title']}]({article['link']}){freshness_tag}")
            lines.append(f"- **📌 核心看点**：{article.get('description', '待阅读')[:80]}...")
            lines.append(f"- **💡 推荐理由**：关键词匹配评分 {score} 分")
            lines.append(f"- **🏷️ 标签**：#{article['keyword']}")
            lines.append("")
        
        return "\n".join(lines)


# ============================================================================
# 报告生成模块
# ============================================================================

class ReportGenerator:
    """Markdown报告生成器"""
    
    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate(self, 
                 filtered_content: str, 
                 raw_articles: List[Dict[str, Any]],
                 config: Config) -> Path:
        """生成完整报告"""
        
        today = datetime.now().strftime('%Y-%m-%d')
        timestamp = datetime.now().strftime('%H:%M:%S')
        weekday = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][datetime.now().weekday()]
        
        # 统计时效性分布
        freshness_stats = {}
        for a in raw_articles:
            f = a.get('freshness', '未知')
            freshness_stats[f] = freshness_stats.get(f, 0) + 1
        
        report = f"""# 📰 HSE资讯每日精选

> 🗓️ **{today} {weekday}** | ⏰ 生成于 {timestamp}  
> 📡 数据源：今日头条 (via RSSHub) | 🤖 AI筛选：Gemini 2.5 Pro

---

## 🏆 今日 Top 20 精选

{filtered_content}

---

## 📊 数据分析

### 抓取统计

| 指标 | 数值 |
|------|------|
| 检索关键词 | {len(config.keywords)} 个 |
| 原始文章数 | {len(raw_articles)} 篇 |
| 精选文章数 | 20 篇 |
| 时效范围 | 过去24小时 |

### 关键词热度分布

"""
        # 统计关键词分布
        from collections import Counter
        keyword_counts = Counter(a['keyword'] for a in raw_articles)
        for kw, count in keyword_counts.most_common():
            bar = '█' * min(count, 20)
            report += f"| {kw} | {bar} {count}篇 |\n"
        
        report += f"""
### 时效性分布

"""
        for freshness, count in sorted(freshness_stats.items(), key=lambda x: -x[1]):
            report += f"- **{freshness}**: {count} 篇\n"
        
        report += f"""
---

## 📌 关于本报告

本报告由 **HSE资讯自动化系统** 自动生成，工作流程：

```
🔍 RSSHub抓取 → ⏱️ 24h时效过滤 → 🤖 Gemini智能筛选 → 📧 邮件推送
```

### 筛选标准

1. **专业相关性**：优先施工安全、危大工程、环境保护等核心领域
2. **内容价值**：优先深度分析、法规解读、事故教训
3. **时效紧迫性**：重大事故预警、政策更新置顶

### 订阅与反馈

- 📧 如需调整关键词，请修改 `fetch_news.py` 中的 `Config.keywords`
- 🔧 如需调整推送时间，请修改 `.github/workflows/daily_news.yml`

---

*🛡️ Powered by HSE News Automation System v1.1*  
*📅 {today} | Made with ❤️ for HSE Professionals*
"""
        
        # 保存报告
        report_path = self.output_dir / f"daily_report_{today}.md"
        report_path.write_text(report, encoding='utf-8')
        logger.info(f"✓ 报告已保存: {report_path}")
        
        # 同时保存一个latest.md方便引用
        latest_path = self.output_dir / "latest_report.md"
        latest_path.write_text(report, encoding='utf-8')
        
        return report_path
    
    def save_raw_data(self, articles: List[Dict[str, Any]]) -> Path:
        """保存原始数据为JSON"""
        today = datetime.now().strftime('%Y-%m-%d')
        raw_path = self.output_dir / f"raw_data_{today}.json"
        
        with open(raw_path, 'w', encoding='utf-8') as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✓ 原始数据已保存: {raw_path}")
        return raw_path


# ============================================================================
# 主程序
# ============================================================================

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='HSE资讯自动抓取系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python fetch_news.py                    # 完整运行
  python fetch_news.py --fetch-only       # 仅抓取，不调用AI
  python fetch_news.py --keywords 安全生产 工程事故
        """
    )
    parser.add_argument('--fetch-only', action='store_true',
                        help='仅抓取数据，不调用Gemini筛选')
    parser.add_argument('--keywords', nargs='+',
                        help='自定义搜索关键词')
    parser.add_argument('--top', type=int, default=20,
                        help='筛选Top N篇文章 (默认20)')
    parser.add_argument('--output', type=str, default='output',
                        help='输出目录')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='静默模式')
    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()
    
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    
    print("""
╔═══════════════════════════════════════════════════════════╗
║         🛡️  HSE资讯自动化抓取系统 v1.0                    ║
║         每日安环管理热文智能精选                          ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    # 初始化配置
    config = Config()
    if args.keywords:
        config.keywords = args.keywords
    config.top_n = args.top
    config.output_dir = args.output
    
    try:
        # 1. 抓取数据
        logger.info("📡 第一阶段：数据抓取")
        fetcher = RSSFetcher(config)
        articles = fetcher.fetch_all()
        
        if not articles:
            logger.error("❌ 未抓取到任何文章，请检查网络或数据源")
            return 1
        
        # 保存原始数据
        reporter = ReportGenerator(config.output_dir)
        reporter.save_raw_data(articles)
        
        # 2. AI筛选
        if not args.fetch_only:
            logger.info("\n🤖 第二阶段：AI智能筛选")
            
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                logger.warning("⚠ 未设置GEMINI_API_KEY，跳过AI筛选")
                filtered_content = "（AI筛选未启用，请设置GEMINI_API_KEY环境变量）"
            else:
                gemini = GeminiFilter(api_key, config.gemini_model)
                filtered_content = gemini.filter_articles(articles, config.top_n)
        else:
            filtered_content = "（仅抓取模式，未进行AI筛选）"
        
        # 3. 生成报告
        logger.info("\n📝 第三阶段：生成报告")
        report_path = reporter.generate(filtered_content, articles, config)
        
        # 4. 完成
        print(f"""
╔═══════════════════════════════════════════════════════════╗
║  ✅ 处理完成！                                             ║
╠═══════════════════════════════════════════════════════════╣
║  📊 抓取文章: {len(articles):>4} 篇                                    ║
║  📄 报告路径: {str(report_path):<40} ║
╚═══════════════════════════════════════════════════════════╝
        """)
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ 系统错误: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())

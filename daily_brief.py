#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project PureFocus - 微信公众号自动化情报系统 (Selenium版)
核心逻辑: 调用本地Chrome访问搜狗微信，搜索并提取最新文章，最后发送邮件。
"""

import os
import sys
import time
import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# 导入邮件模块
try:
    from send_email import EmailSender
except ImportError:
    print("❌ 错误: 未找到 send_email.py 模块")
    sys.exit(1)

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ================= 配置区域 =================

# 1. 搜索间隔 (秒) - 必须设置长一点，防止被封 IP
DELAY_MIN = 5
DELAY_MAX = 10

# 2. 公众号清单 (30个)
ACCOUNTS = [
    # A组
    ("筑龙施工", "施工技术", "方案/工法"),
    ("HSE研习社", "安全管理", "体系/标准"),
    ("豆丁施工", "施工资源", "文档库"),
    ("安全科", "安全实操", "检查表"),
    ("建筑管理", "宏观政策", "项目管理"),
    ("每日安全生产事故通报", "警示教育", "事故案例"),
    ("中国安全生产网", "官方法规", "国家发布"),
    ("土木工程", "基础理论", "结构技术"),
    ("基建通", "市场动态", "招投标"),
    ("施工技术", "前沿工艺", "学术论文"),
    # B组
    ("工程众生相", "深度评论", "行业观察"),
    ("胖栋有话说", "落地实操", "痛点分析"),
    ("建设法律人", "法律纠纷", "索赔签证"),
    ("工地艺哥", "技术图解", "手绘节点"),
    ("通俗易懂学安全", "科普培训", "素材库"),
    ("土木小生", "成长笔记", "一线经验"),
    ("周sir的HSE视界", "海外/外企", "高端经验"),
    ("工程大队队长", "行业吐槽", "幽默解压"),
    ("结构小站", "结构配合", "设计视角"),
    ("老王说水利", "水利专家", "细分领域"),
    # C组
    ("墨子连山", "造价法律", "扯皮/合同"),
    ("土木吧", "行业内幕", "爆料/吐槽"),
    ("非解构", "结构技术", "设计原理"),
    ("施工企业法务", "乙方维权", "索赔/霸王条款"),
    ("HSEman", "硬核安全", "力学计算/方案"),
    ("强哥说造价", "造价实操", "算量/对账"),
    ("路桥人", "路桥市政", "技术交流"),
    ("项目经理智囊团", "PM软技能", "协调/成本"),
    ("一间房", "新技术", "BIM/装配式"),
    ("土木坛子", "职场思考", "海外/转行")
]

# 3. 24小时时间戳
TIME_CUTOFF = datetime.now() - timedelta(hours=24)

class SogouScraper:
    def __init__(self):
        self.driver = None
        self.init_driver()

    def init_driver(self):
        """初始化 Chrome 驱动"""
        logger.info("🔧 正在启动 Chrome 浏览器...")
        options = webdriver.ChromeOptions()
        # CI 环境自动启用 headless；本地调试需人工过验证码
        if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
            options.add_argument("--headless")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-extensions")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--mute-audio")
        
        # 规避 Selenium 检测
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            
            # 进一步规避检测
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                    })
                """
            })
            
            self.driver.maximize_window()
        except Exception as e:
            logger.error(f"❌ 启动浏览器失败: {e}")
            sys.exit(1)

    def search_account(self, name, tag, reason) -> Dict:
        """搜索单个公众号，返回最新且在24小时内的文章"""
        search_url = f"https://weixin.sogou.com/weixin?type=1&query={name}&ie=utf8"
        
        try:
            self.driver.get(search_url)
            
            # 等待结果加载，如果出现验证码，需要人工处理
            # 简单判断: 检查是否有结果列表
            try:
                # 等待第一个结果出现
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".news-box .txt-box"))
                )
            except TimeoutException:
                # 可能是验证码页面，或者是没结果
                if "antispider" in self.driver.current_url:
                    logger.warning("⚠️ 出现搜狗验证码！请在浏览器中手动完成验证...")
                    # 循环等待直到验证码消失
                    while "antispider" in self.driver.current_url:
                        time.sleep(2)
                    logger.info("✅ 验证通过，继续...")
                    # 重新加载
                    self.driver.get(search_url)
                else:
                    logger.warning(f"⚠️ 未找到公众号: {name}")
                    return None

            # 抓取第一个结果（通常是最匹配的）
            results = self.driver.find_elements(By.CSS_SELECTOR, ".news-box .txt-box")
            if not results:
                return None
                
            first_result = results[0]
            
            # 提取公众号名称确认是否匹配 (模糊匹配)
            # tit = first_result.find_element(By.CSS_SELECTOR, ".tit").text
            
            # 提取最新文章信息
            # 结构: dt -> 链接/标题, dd -> 简介/时间
            try:
                # 注意：搜狗结果里，最新文章通常在 <dl> 下
                # 很多时候直接显示 "最新文章：" 链接
                # Selector: dl:last-child a
                
                latest_link_elem = first_result.find_element(By.CSS_SELECTOR, "dl a")
                title = latest_link_elem.text
                link = latest_link_elem.get_attribute("href")
                
                # 时间处理: 搜狗搜索页的时间显示比较复杂，有时是 "1小时前", "昨天", 或者时间戳
                # 实际上搜狗搜索列表页显示的通常是“最近文章”，但没有精确时间戳
                # 我们只能先抓取，假设它是最新的。为了精准，我们需要点进去吗？
                # 点进去风险太大。
                # 策略：搜狗搜索列表页有一行灰色的字: 
                # <span class="s2"><script>document.write(timeConvert('1738402235'))</script></span>
                # 这是一个 JS 渲染的时间戳。
                
                # 尝试找到时间戳脚本
                time_script = first_result.find_element(By.CSS_SELECTOR, "dl dd span.s2 script").get_attribute("innerHTML")
                # 提取数字 e.g. "timeConvert('1738402235')"
                import re
                ts_match = re.search(r"timeConvert\('(\d+)'\)", time_script)
                if ts_match:
                    ts = int(ts_match.group(1))
                    pub_time = datetime.fromtimestamp(ts)
                    
                    # 判断是否在24小时内
                    if pub_time >= TIME_CUTOFF:
                        logger.info(f"✅ [{name}] 发现新文: {title} ({pub_time.strftime('%H:%M')})")
                        return {
                            "title": title,
                            "link": link,
                            "author": name,
                            "tag": tag,
                            "reason": reason,
                            "pub_time": pub_time
                        }
                    else:
                        logger.info(f"   [{name}] 最新文章较旧 ({pub_time.strftime('%m-%d')})")
                        return None
                else:
                    # 没找到时间戳，保险起见跳过
                    return None

            except NoSuchElementException:
                # 没有最新文章部分
                logger.info(f"   [{name}] 未显示最新文章")
                return None
                
        except Exception as e:
            logger.error(f"❌ 搜索出错 {name}: {e}")
            return None
        return None

    def close(self):
        if self.driver:
            self.driver.quit()

def generate_report(articles: List[Dict]) -> str:
    """生成Markdown简报"""
    if not articles:
        return ""
        
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    md = [f"# 📑 HSE与工程行业每日情报 ({len(articles)}篇)",
          f"> 生成时间: {now_str}",
          f"> 来源: Project PureFocus (Chrome Automation)",
          ""]
    
    for idx, art in enumerate(articles, 1):
        time_str = art['pub_time'].strftime('%m-%d %H:%M')
        md.append(f"### {idx}. [{art['tag']}] {art['title']}")
        md.append(f"- **公众号**: {art['author']}")
        md.append(f"- **发布**: {time_str}")
        md.append(f"- **推荐**: {art['reason']}")
        md.append(f"- **链接**: [点击阅读]({art['link']})")
        md.append("---")
    
    md.append("\n> Generated by Gemini Agent via Selenium")
    return "\n".join(md)

def main():
    print("🚀 Project PureFocus (Selenium版) 启动中...")
    print("⚠️  注意: 将自动打开 Chrome 浏览器。请勿关闭窗口！")
    print("⚠️  如果出现搜狗验证码，请手动滑动滑块！程序会自动检测并继续。")
    print("-" * 50)
    
    scraper = SogouScraper()
    valid_articles = []
    
    try:
        total = len(ACCOUNTS)
        for i, (name, tag, reason) in enumerate(ACCOUNTS, 1):
            print(f"[{i}/{total}] 正在检索: {name} ...")
            
            art = scraper.search_account(name, tag, reason)
            if art:
                valid_articles.append(art)
            
            # 随机延时
            if i < total:
                sleep_time = random.uniform(DELAY_MIN, DELAY_MAX)
                # print(f"   休息 {sleep_time:.1f} 秒...")
                time.sleep(sleep_time)
                
    finally:
        scraper.close()
        
    print("-" * 50)
    print(f"📊 检索完成。发现 {len(valid_articles)} 篇 24小时内的新文章。")
    
    if not valid_articles:
        print("📭 今日无更新，结束。")
        return

    # 生成和发送
    report_md = generate_report(valid_articles)
    
    # 保存
    os.makedirs("output", exist_ok=True)
    report_file = f"output/brief_{datetime.now().strftime('%Y%m%d')}.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report_md)
        
    # 发送
    sender = EmailSender()
    to_email = os.getenv('MAIL_TO') or os.getenv('MAIL_USERNAME')
    
    if to_email:
        subject = f"📰 [PureFocus] 行业情报 ({len(valid_articles)}条) - {datetime.now().strftime('%m-%d')}"
        sender.send_markdown_report(to_email, subject, report_md, from_name="PureFocus情报官")
    else:
        print("❌ 未设置邮箱，跳过发送")

if __name__ == "__main__":
    main()

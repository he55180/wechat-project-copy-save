#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Copy-Save: Wechat Project Copy-Save (Markdown + Word + 英文文件名)
功能：读取剪贴板 -> 清洗 -> 翻译文件名 -> 转MD -> 转Word
"""

import os
import sys
import re
import time
import shutil
import subprocess
import requests
import pyperclip
import html2text
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 加载 .env（必须用绝对路径）
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

# ================= 配置 =================
BASE = Path(__file__).parent
CHINESE_DOCX_DIR = BASE.parent / "chinese-docx-auto-typesetting"
PREPROCESS_PATH = CHINESE_DOCX_DIR / "preprocess_md.py"
FORMAT_EXPERT_PATH = CHINESE_DOCX_DIR / "format_expert.py"
GOLDEN_TEMPLATE = CHINESE_DOCX_DIR / "templates" / "黄金模板.docx"

# 保存路径 (从 .env 读取 SAVE_DIR，默认 output 目录)
SAVE_DIR = os.environ.get("SAVE_DIR", str(BASE / "output"))

# 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.60 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF XWEB/6939"
}
# ========================================

def clean_filename(title):
    """清理文件名中的非法字符"""
    return re.sub(r'[\\/:*?"<>|]', '_', title).strip()

def get_session():
    """创建带有重试机制的会话"""
    session = requests.Session()
    retry = Retry(
        total=3, 
        read=3, 
        connect=3, 
        backoff_factor=1, 
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    session.headers.update(HEADERS)
    return session

def save_article(url):
    print(f"🔗 检测到链接: {url}")
    print("⏳ 正在请求文章内容 (已启用重试机制)...")
    
    try:
        session = get_session()
        resp = session.get(url, timeout=30)
        if resp.status_code != 200:
             print(f"❌ 服务器返回错误: {resp.status_code}")
             return False
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        print("💡 建议：网络可能不稳定，请稍后重试一次。")
        return False

    soup = BeautifulSoup(resp.content, "html.parser")
    
    # 1. 提取元数据
    try:
        title = soup.find("meta", property="og:title")["content"]
    except:
        try:
            title = soup.find(id="activity-name").get_text(strip=True)
        except:
            title = "未知标题_" + str(int(time.time()))
    
    try:
        profile_name = soup.find(id="js_name").get_text(strip=True)
    except:
        profile_name = "公众号"

    print(f"📄 标题: {title}")
    
    # === 文件名使用原标题 (不翻译) ===
    title_final = clean_filename(title)
    
    # 2. 提取并修复正文
    content_div = soup.find(id="js_content")
    if not content_div:
        content_div = soup.find(class_="rich_media_content")
        
    if not content_div:
        print("⚠️ 未找到正文区域，可能不是标准的公众号文章。")
        return False

    # 3. 预处理 (Anti-Lazyload)
    imgs = content_div.find_all("img")
    count = 0
    for img in imgs:
        if img.get("data-src"):
            img["src"] = img["data-src"]
            del img["data-src"]
            count += 1
    print(f"🖼️ 已保留图片链接: {count} 张")

    # 4. 转换为 Markdown
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = False
    converter.ignore_tables = False
    converter.body_width = 0 
    
    html_str = str(content_div)
    md_content = converter.handle(html_str)
    
    # 5. 组装最终文档
    today_str = datetime.now().strftime("%Y-%m-%d")
    final_md = f"""# {title}

> **来源**: {profile_name}
> **归档日期**: {today_str}
> **原文链接**: [{url}]({url})

---

{md_content}

---
*Created by Project Copy-Save*
"""

    # 6. 保存文件 (Markdown)
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)

    # === 使用原标题作为文件名 ===
    filename_base = f"[{today_str}] {title_final}"
    filename_md = f"{filename_base}.md"
    filename_docx = f"{filename_base}.docx"
    
    file_path_md = os.path.join(SAVE_DIR, filename_md)
    file_path_docx = os.path.join(SAVE_DIR, filename_docx)
    
    if os.path.exists(file_path_md):
        print("⚠️ 文件已存在，自动覆盖...")

    with open(file_path_md, "w", encoding="utf-8") as f:
        f.write(final_md)
        
    print(f"✅ Markdown 保存成功: {filename_md}")
    
    # 7. 三步管线：预处理 → Pandoc → 精确排版
    print("⏳ 正在生成 Word 文档 (GB/T 9704-2012 标准)...")
    try:
        escaped_md = file_path_md.replace(".md", "_escaped.md")
        temp_docx  = file_path_md.replace(".md", "_temp.docx")

        # Step 1: 预处理 Markdown
        try:
            subprocess.run(
                [sys.executable, str(PREPROCESS_PATH), file_path_md, escaped_md],
                check=True, capture_output=True, text=True
            )
            print("   [1/3] Markdown 预处理完成")
        except subprocess.CalledProcessError as e:
            print(f"   [1/3] 预处理失败: {e.stderr}")
            # Fallback: 跳过预处理，直接用原始 MD
            escaped_md = file_path_md
            print("   ↳ 跳过预处理，使用原始 Markdown")

        # Step 2: Pandoc 转 docx
        try:
            pandoc_cmd = ["pandoc", escaped_md, "-o", temp_docx]
            if GOLDEN_TEMPLATE.exists():
                pandoc_cmd.extend(["--reference-doc", str(GOLDEN_TEMPLATE)])
            subprocess.run(pandoc_cmd, check=True, capture_output=True, text=True)
            print("   [2/3] Pandoc 转换完成")
        except FileNotFoundError:
            print("⚠️ 未找到 pandoc，仅保存 Markdown。安装: choco install pandoc / apt install pandoc")
            return True
        except subprocess.CalledProcessError as e:
            print(f"   [2/3] Pandoc 失败: {e.stderr}")
            # 无模板重试
            pandoc_cmd = ["pandoc", escaped_md, "-o", temp_docx]
            subprocess.run(pandoc_cmd, check=True, capture_output=True, text=True)
            print("   ↳ 无模板重试成功")

        # Step 3: format_expert.py 精确排版
        try:
            subprocess.run(
                [sys.executable, str(FORMAT_EXPERT_PATH), temp_docx, "-o", file_path_docx],
                check=True, capture_output=True, text=True
            )
            print("   [3/3] GB/T 9704-2012 排版完成")
        except subprocess.CalledProcessError as e:
            print(f"   [3/3] 排版失败: {e.stderr}")
            # Fallback: 使用 Pandoc 生成的原始 docx
            import shutil
            shutil.copy(temp_docx, file_path_docx)
            print("   ↳ 回退到基础 Pandoc 版本")

        # 清理临时文件
        for f in [escaped_md, temp_docx]:
            if os.path.exists(f) and f != file_path_md:
                os.remove(f)

        print(f"✅ Word 保存成功: {filename_docx}")
        print(f"📍 文件位置: {SAVE_DIR}")

    except Exception as e:
        print(f"❌ 转换出错: {e}")
        return False

    return True

def main():
    print("="*40)
    print("      Project Copy-Save | 一键归档 (Global版)")
    print("="*40)
    
    try:
        content = pyperclip.paste()
    except Exception as e:
        print(f"❌ 读取剪贴板失败: {e}")
        return

    if not content:
        print("📭 剪贴板为空！")
        return
        
    url_match = re.search(r'(https://mp\.weixin\.qq\.com/s/[a-zA-Z0-9_\-]+)', content)
    
    if not url_match:
         if "mp.weixin.qq.com" in content and "http" in content:
             url = content.strip()
         else:
             print("📭 未发现有效链接。")
             return
    else:
        url = url_match.group(0)

    success = save_article(url)
    
    if success:
        time.sleep(2)
    else:
        print("\n按任意键退出...")
        # os.system("pause >nul") # 如有需要可取消注释

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邮件发送模块
============
用于本地测试邮件发送功能

GitHub Actions中使用 dawidd6/action-send-mail 插件
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Optional

import markdown
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class EmailSender:
    """邮件发送器"""
    
    def __init__(self, 
                 smtp_server: str = "smtp.gmail.com",
                 smtp_port: int = 587,
                 username: str = None,
                 password: str = None):
        """
        初始化邮件发送器
        
        Args:
            smtp_server: SMTP服务器地址
            smtp_port: SMTP端口
            username: 发送邮箱
            password: 应用专用密码
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username or os.getenv('MAIL_USERNAME')
        self.password = password or os.getenv('MAIL_PASSWORD')
        
        if not self.username or not self.password:
            raise ValueError("请设置MAIL_USERNAME和MAIL_PASSWORD环境变量")
    
    def send_markdown_report(self,
                             to_email: str,
                             subject: str,
                             markdown_content: str,
                             from_name: str = "HSE资讯机器人") -> bool:
        """
        发送Markdown格式的报告邮件
        
        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            markdown_content: Markdown格式的正文
            from_name: 发件人显示名称
        
        Returns:
            是否发送成功
        """
        try:
            # 创建邮件
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{from_name} <{self.username}>"
            msg['To'] = to_email
            
            # 纯文本版本
            text_part = MIMEText(markdown_content, 'plain', 'utf-8')
            
            # HTML版本（Markdown转换）
            html_content = self._markdown_to_html(markdown_content)
            html_part = MIMEText(html_content, 'html', 'utf-8')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # 发送邮件
            logger.info(f"📧 正在发送邮件到: {to_email}")
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            logger.info("✓ 邮件发送成功！")
            return True
            
        except smtplib.SMTPAuthenticationError:
            logger.error("✗ 认证失败：请检查邮箱和应用专用密码")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"✗ SMTP错误: {e}")
            return False
        except Exception as e:
            logger.error(f"✗ 发送失败: {e}")
            return False
    
    def _markdown_to_html(self, md_content: str) -> str:
        """将Markdown转换为带样式的HTML"""
        
        # 转换Markdown为HTML
        html_body = markdown.markdown(
            md_content,
            extensions=['tables', 'fenced_code', 'nl2br']
        )
        
        # 添加CSS样式
        html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #1a73e8;
            border-bottom: 3px solid #1a73e8;
            padding-bottom: 15px;
            margin-bottom: 25px;
        }}
        h2 {{
            color: #34a853;
            margin-top: 30px;
            padding-top: 15px;
            border-top: 1px solid #eee;
        }}
        h3 {{
            color: #5f6368;
        }}
        a {{
            color: #1a73e8;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
        }}
        tr:nth-child(even) {{
            background: #fafafa;
        }}
        code {{
            background: #f1f3f4;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
        }}
        pre {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            overflow-x: auto;
        }}
        blockquote {{
            border-left: 4px solid #1a73e8;
            margin: 20px 0;
            padding-left: 20px;
            color: #5f6368;
        }}
        .emoji {{
            font-size: 1.2em;
        }}
        hr {{
            border: none;
            border-top: 1px solid #eee;
            margin: 30px 0;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 2px solid #eee;
            color: #666;
            font-size: 12px;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        {html_body}
        <div class="footer">
            <p>📬 本邮件由 <strong>HSE资讯自动化系统</strong> 自动生成并发送</p>
            <p>如需退订或修改设置，请联系管理员</p>
        </div>
    </div>
</body>
</html>
"""
        return html_template
    
    def send_report_file(self, 
                         to_email: str, 
                         report_path: str,
                         subject: str = None) -> bool:
        """
        发送报告文件
        
        Args:
            to_email: 收件人
            report_path: 报告文件路径
            subject: 邮件主题（默认从文件名生成）
        """
        path = Path(report_path)
        
        if not path.exists():
            logger.error(f"✗ 报告文件不存在: {path}")
            return False
        
        content = path.read_text(encoding='utf-8')
        
        if subject is None:
            from datetime import datetime
            today = datetime.now().strftime('%Y-%m-%d')
            subject = f"📰 [HSE日报] 今日安环管理热文精选 - {today}"
        
        return self.send_markdown_report(to_email, subject, content)


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='发送HSE日报邮件')
    parser.add_argument('report', nargs='?', default='output/latest_report.md',
                        help='报告文件路径')
    parser.add_argument('-t', '--to', dest='to_email',
                        help='收件人邮箱（默认使用MAIL_TO或MAIL_USERNAME）')
    parser.add_argument('-s', '--subject', help='邮件主题')
    
    args = parser.parse_args()
    
    to_email = args.to_email or os.getenv('MAIL_TO') or os.getenv('MAIL_USERNAME')
    
    if not to_email:
        print("❌ 请指定收件人邮箱（-t 参数或 MAIL_TO 环境变量）")
        return 1
    
    try:
        sender = EmailSender()
        success = sender.send_report_file(to_email, args.report, args.subject)
        return 0 if success else 1
    except Exception as e:
        logger.error(f"❌ 错误: {e}")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())

import os
import sys
import json
import time
import logging
import traceback
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file at the very beginning
load_dotenv()

import requests
import feedparser
import google.generativeai as genai
from dateutil import parser as date_parser
from tenacity import retry, stop_after_attempt, wait_exponential

# --- Enhanced Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

# --- Constants ---
OUTPUT_DIR = "output"
STABLE_GEMINI_MODEL = "gemini-1.5-flash"
GROQ_MODEL = "llama3-70b-8192"

# --- API Key Management ---
def load_gemini_keys() -> List[str]:
    """Load multiple Gemini API keys from environment variables."""
    keys_str = os.getenv('GEMINI_API_KEYS', '')
    if keys_str:
        keys = [k.strip() for k in keys_str.split(',') if k.strip()]
        if keys:
            logger.info(f"Loaded {len(keys)} Gemini API key(s) for rotation.")
            return keys
    single_key = os.getenv('GEMINI_API_KEY', '')
    if single_key:
        logger.info("Loaded a single Gemini API key.")
        return [single_key]
    logger.warning("No Gemini API keys found.")
    return []

GEMINI_API_KEYS = load_gemini_keys()
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
_current_gemini_key_index = 0

def get_next_gemini_key() -> str:
    """Rotate to the next available Gemini API key."""
    global _current_gemini_key_index
    if not GEMINI_API_KEYS:
        return ''
    key = GEMINI_API_KEYS[_current_gemini_key_index]
    _current_gemini_key_index = (_current_gemini_key_index + 1) % len(GEMINI_API_KEYS)
    return key

# --- AI Callers with Failover ---
def call_gemini(api_key: str, prompt: str) -> str:
    """Makes a single call to the Gemini API."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(STABLE_GEMINI_MODEL)
    response = model.generate_content(prompt)
    return response.text

def call_groq(prompt: str) -> str:
    """Makes a single call to the Groq API."""
    logger.info("    -> Attempting Groq API call...")
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={"model": GROQ_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2, "max_tokens": 8192},
        timeout=60
    )
    response.raise_for_status()
    logger.info("    <- Groq call successful.")
    return response.json()["choices"][0]["message"]["content"]

def call_ai_with_failover(prompt: str) -> str:
    """
    Calls an AI model with a defined failover strategy.
    1. Tries all available Gemini keys in rotation.
    2. If all Gemini keys fail, it falls back to Groq as a backup.
    """
    logger.info("    Attempting to call AI with failover strategy...")
    last_gemini_error = None

    # 1. Prioritize Gemini with key rotation
    if GEMINI_API_KEYS:
        logger.info(f"    Starting with Gemini, {len(GEMINI_API_KEYS)} key(s) available for rotation.")
        for i in range(len(GEMINI_API_KEYS)):
            api_key = get_next_gemini_key()
            try:
                logger.info(f"    -> Attempting Gemini with key #{_current_gemini_key_index}...")
                result = call_gemini(api_key, prompt)
                logger.info("    <- Gemini call successful.")
                return result
            except Exception as e:
                last_gemini_error = e
                logger.warning(f"    <- Gemini key #{_current_gemini_key_index} failed. Reason: {type(e).__name__}. Rotating...")
        logger.warning("    All Gemini keys have been tried and failed.")
    else:
        logger.warning("    No Gemini API keys configured. Proceeding directly to Groq.")

    # 2. Fallback to Groq if all Gemini attempts fail
    if GROQ_API_KEY:
        logger.info("    Falling back to Groq engine...")
        try:
            return call_groq(prompt)
        except Exception as groq_error:
            logger.error("    FATAL: Fallback engine Groq also failed.")
            logger.error(f"    Groq Error: {groq_error}")
            if last_gemini_error:
                logger.error(f"    Last Gemini Error: {last_gemini_error}")
                raise last_gemini_error from groq_error
            raise groq_error
    
    # 3. If everything fails
    logger.critical("FATAL: All AI API calls failed. No Gemini or Groq keys are configured or working.")
    raise ValueError("All AI models (Gemini and Groq) failed or are not configured.")

# --- Stage 1: AI Query Generation ---
def generate_search_queries() -> List[str]:
    logger.info("--- STAGE 1: GENERATE QUERIES ---")
    try:
        logger.info("Calling AI to generate queries...")
        prompt = """生成10个中文搜索关键词，用于搜索建筑施工安全、工程技术、环境管理相关的新闻。
要求：必须是中文关键词，简短有效（2-6个字）
仅输出JSON数组，不要解释。示例格式：
["施工安全", "高处作业", "基坑支护"]"""
        
        response_text = call_ai_with_failover(prompt)
        
        logger.info("Parsing AI response...")
        clean_text = response_text.strip()
        if '```' in clean_text:
            import re
            match = re.search(r'\[.*?\]', clean_text, re.DOTALL)
            clean_text = match.group() if match else clean_text
        
        queries = json.loads(clean_text)
        logger.info(f"Successfully generated {len(queries)} queries.")
        return queries
    except Exception as e:
        logger.error(f"!!! STAGE 1 FAILED: Could not generate search queries via any AI model.")
        logger.error(f"    Final Error: {e}")
        logger.error("    Falling back to default queries.")
        return ["施工安全", "建筑工程安全", "危大工程", "环保施工", "事故案例分析", "高处作业安全", "起重吊装事故", "基坑支护安全", "建筑消防管理", "绿色施工技术"]

# --- Stage 2: RSS Fetching ---
class RssFetcher:
    def __init__(self):
        self.session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
        self.session.headers.update(headers)

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, max=5))
    def _fetch_url(self, url: str):
        logger.info(f"    Fetching URL: {url}")
        response = self.session.get(url, timeout=15)
        response.raise_for_status()
        return response

    def fetch_articles_for_query(self, query: str) -> List[Dict[str, Any]]:
        encoded_kw = urllib.parse.quote(query)
        sources = [
            f"https://news.google.com/rss/search?q={encoded_kw}&hl=zh-CN&gl=CN",
            f"https://www.bing.com/news/search?q={encoded_kw}&format=rss&mkt=zh-CN"
        ]
        articles = []
        for url in sources:
            try:
                response = self._fetch_url(url)
                feed = feedparser.parse(response.text)
                for entry in feed.entries:
                    pub_date = date_parser.parse(entry.get('published', '')) if entry.get('published') else datetime.now(timezone.utc)
                    if (datetime.now(timezone.utc) - pub_date.astimezone(timezone.utc)) > timedelta(days=14):
                        continue
                    articles.append({'title': entry.get('title', ''), 'link': entry.get('link', ''), 'description': entry.get('summary', '')[:200]})
            except Exception as e:
                logger.warning(f"    Could not fetch or parse RSS feed {url}. Reason: {e}")
        return articles

    def fetch_all(self, queries: List[str]) -> List[Dict[str, Any]]:
        logger.info("--- STAGE 2: FETCH ARTICLES ---")
        all_articles = []
        seen_links = set()
        for i, query in enumerate(queries):
            logger.info(f"  -> Processing query {i+1}/{len(queries)}: '{query}'")
            articles_for_query = self.fetch_articles_for_query(query)
            logger.info(f"     Found {len(articles_for_query)} raw articles.")
            for article in articles_for_query:
                if article.get('link') and article['link'] not in seen_links:
                    all_articles.append(article)
                    seen_links.add(article['link'])
            time.sleep(0.2)
        logger.info(f"Total unique articles fetched: {len(all_articles)}")
        return all_articles

# --- Stage 3: AI Summarization ---
def summarize_and_format(articles: List[Dict[str, Any]]) -> str:
    logger.info("--- STAGE 3: SUMMARIZE WITH AI ---")
    if not articles:
        logger.warning("No articles to summarize.")
        return "# Daily HSE Briefing\n\n- No relevant articles were found today."
        
    try:
        limited_articles = articles[:25]
        logger.info(f"Processing {len(limited_articles)} of {len(articles)} articles...")
        
        articles_text = "\n".join([f"{i+1}. {article['title'][:80]} | {article['link']}" for i, article in enumerate(limited_articles)])
        
        prompt = f"""你是一位资深HSE总监。从以下新闻列表中选出最有价值的10篇，为施工现场管理人员提供简报。
用中文Markdown格式输出，每篇包含：
### 标题
- 核心要点（1-2句话）
- 管理启示
- [原文链接](URL)

新闻列表：
{articles_text}"""
        
        logger.info("Calling AI to summarize articles...")
        response_text = call_ai_with_failover(prompt)
        logger.info("Successfully summarized articles.")
        return f"# HSE每日资讯简报\n\n生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n---\n\n{response_text}"
    except Exception as e:
        logger.error("!!! STAGE 3 FAILED: Could not summarize articles via any AI model.")
        logger.error(f"    Final Error: {e}")
        return f"# AI Summarization Failed\n\nAn error occurred during the final analysis step:\n\n```\n{e}\n```"

# --- Main Orchestrator ---
def main():
    logger.info("--- SCRIPT START ---")
    
    if not GEMINI_API_KEYS and not GROQ_API_KEY:
        logger.critical("!!! CRITICAL ERROR: No AI API keys (GEMINI or GROQ) found in environment!")
        return 1

    try:
        queries = generate_search_queries()
        fetcher = RssFetcher()
        raw_articles = fetcher.fetch_all(queries)
        final_report = summarize_and_format(raw_articles)
        
        logger.info("--- SAVING REPORT ---")
        output_path = Path(OUTPUT_DIR)
        output_path.mkdir(exist_ok=True)
        report_file = output_path / "latest_report.md"
        report_file.write_text(final_report, encoding='utf-8')
        logger.info(f"Report saved to {report_file}")
        
        logger.info("--- SCRIPT SUCCESS ---")
        return 0

    except Exception as e:
        logger.critical("!!! UNHANDLED CRITICAL ERROR IN MAIN EXECUTION !!!")
        logger.critical(traceback.format_exc())
        return 1

if __name__ == '__main__':
    sys.exit(main())
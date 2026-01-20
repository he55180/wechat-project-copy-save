import os
import sys
import json
import time
import logging
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any

import requests
import feedparser
from google import genai
from google.generativeai import types
from dateutil import parser as date_parser
from tenacity import retry, stop_after_attempt, wait_exponential

# --- Basic Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

OUTPUT_DIR = "output"
STABLE_GEMINI_MODEL = "gemini-pro"
API_KEY = os.getenv('GEMINI_API_KEY')

# --- Stage 1: AI as a Query Generator ---
def generate_search_queries(api_key: str) -> List[str]:
    logger.info("🤖 Stage 1: AI is generating smart search queries...")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(STABLE_GEMINI_MODEL)
    
    prompt = """
    Based on the goal of finding in-depth articles for a construction HSE (Health, Safety, Environment) director, generate 10 diverse and specific search query strings.
    Focus on:
    - Advanced construction techniques and safety protocols.
    - Case studies of engineering failures or successes.
    - Environmental management on construction sites.
    - Risk assessment for complex projects.
    - Target sources like engineering blogs, professional discussions, and expert columns.

    Provide the output as a simple JSON list of strings. Example: ["query1", "query2", ...].
    Do not include any other text in your response.
    """
    
    try:
        response = model.generate_content(prompt)
        queries = json.loads(response.text)
        logger.info(f"✅ AI generated {len(queries)} queries.")
        return queries
    except Exception as e:
        logger.error(f"❌ Failed to generate queries: {e}. Using fallback queries.")
        return ["施工安全", "建筑工程安全", "危大工程", "环保施工", "事故案例分析"]

# --- Stage 2: RSS Fetcher ---
class RssFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, max=5))
    def _fetch_url(self, url: str):
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
                    pub_date = date_parser.parse(entry.get('published', '')) if entry.get('published') else datetime.now()
                    if datetime.now() - pub_date > timedelta(days=7):
                        continue
                    articles.append({
                        'title': entry.get('title', ''),
                        'link': entry.get('link', ''),
                        'description': entry.get('summary', '')[:200],
                        'keyword': query
                    })
            except Exception as e:
                logger.warning(f"Could not fetch RSS feed {url}: {e}")
        return articles

    def fetch_all(self, queries: List[str]) -> List[Dict[str, Any]]:
        logger.info("📡 Stage 2: Fetching articles from RSS sources...")
        all_articles = []
        seen_links = set()
        for query in queries:
            logger.info(f"  -> Searching for: {query}")
            for article in self.fetch_articles_for_query(query):
                if article['link'] not in seen_links:
                    all_articles.append(article)
                    seen_links.add(article['link'])
            time.sleep(0.5)
        logger.info(f"✅ Fetched {len(all_articles)} unique articles.")
        return all_articles

# --- Stage 3: AI as Summarizer ---
def summarize_and_format(api_key: str, articles: List[Dict[str, Any]]) -> str:
    logger.info("🤖 Stage 3: AI is summarizing and filtering...")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(STABLE_GEMINI_MODEL)

    articles_text = "\n\n".join([f"{i+1}. [{article['title']}]({article['link']})\n   Summary: {article['description']}" for i, article in enumerate(articles)])
    
    prompt = f"""
You are an expert HSE Director. From the following list of articles, select the top 20 most valuable ones for a construction site manager. 

    For each selected article, provide a deep analysis in the following Markdown format: 
    
    ---
    
    ### [Article Title](Article URL)
    - **Key Insights**: A bulleted list of the most important takeaways.
    - **Management Application**: Concrete advice on how to apply these insights on a project.
    
    Here are the raw articles:
    {articles_text}
    """
    
    try:
        response = model.generate_content(
            prompt,
            generation_config=types.GenerationConfig(temperature=0.3, max_output_tokens=8192)
        )
        logger.info("✅ AI summarization complete.")
        return response.text
    except Exception as e:
        logger.error(f"❌ AI summarization failed: {e}")
        return f"# AI Summarization Failed\n\nError: {e}"

# --- Main Orchestrator ---
def main():
    logger.info("🚀 Starting HSE News Automation v3.0")
    if not API_KEY:
        logger.error("❌ Critical: GEMINI_API_KEY is not set.")
        sys.exit(1)

    queries = generate_search_queries(API_KEY)
    fetcher = RssFetcher()
    raw_articles = fetcher.fetch_all(queries)

    if not raw_articles:
        logger.warning("⚠️ No articles found. Exiting.")
        final_report = "# No Articles Found\n\nNo relevant articles were found today using AI-generated queries."
    else:
        final_report = summarize_and_format(API_KEY, raw_articles)

    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(exist_ok=True)
    report_file = output_path / "latest_report.md"
    report_file.write_text(final_report, encoding='utf-8')
    logger.info(f"✅ Final report saved to {report_file}")
    
    logger.info("🎉 Process completed.")

if __name__ == '__main__':
    main()

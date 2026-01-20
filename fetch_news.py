import os
import sys
import logging
from pathlib import Path
import google.generativeai as genai
from google.generativeai import types

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

OUTPUT_DIR = "output"
MODEL_NAME = "gemini-1.5-pro-latest" # Using a powerful model for this complex task

# --- The powerful, all-in-one prompt ---
SYSTEM_PROMPT = """
You are an expert research analyst for a senior HSE Director in the construction industry.
Your mission is to find and summarize the most valuable, recent, and in-depth articles on the web.
"""

USER_PROMPT = """
Please perform a web search to find the 20 most insightful and highest-quality articles published in the last 7 days on the following topics:
- Advanced construction technology and techniques
- In-depth case studies of engineering safety incidents
- Best practices in construction site environmental management
- Risk analysis of complex construction projects (e.g., deep excavations, high-rise structures)

CRITERIA:
- **Source Type**: Strongly prefer articles from personal blogs of engineers, industry experts' columns, in-depth forum discussions, and professional journals. AVOID generic news reports, press releases, and product advertisements.
- **Content Quality**: The articles must provide deep insights, practical advice, lessons learned, or detailed technical analysis.

TASK:
For each of the top 20 articles you find, format the output *strictly* in Markdown as follows:

---

### [Article Title](Article URL)
- **Source Type**: (e.g., Engineer's Blog, Professional Journal, Industry Forum)
- **Key Insights**: A concise bulleted list summarizing the core technical points and takeaways.
- **Management Application**: How a construction project manager or HSE director can apply these insights.

Very Important:
- Ensure all links are valid and directly point to the article.
- The entire output must be a single Markdown text block.
- Do not include any introductory or concluding text outside of the Markdown report format.
- Rank the articles with the most valuable and insightful ones first.
"""

def get_hse_briefing(api_key: str) -> str:
    """
    Uses Gemini to perform a web search and generate a complete HSE briefing.
    """
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=SYSTEM_PROMPT
    )
    
    logger.info(f"🤖 Calling Gemini 1.5 Pro to search and generate the report...")
    
    try:
        response = model.generate_content(
            USER_PROMPT,
            generation_config=types.GenerationConfig(
                temperature=0.5,
                max_output_tokens=8192
            )
        )
        logger.info("✅ Gemini task completed successfully.")
        return response.text
    except Exception as e:
        logger.error(f"❌ An error occurred during the Gemini API call: {e}")
        return f"# ⚠️ AI Briefing Generation Failed\n\nAn error occurred while contacting the Gemini API:\n\n```\n{e}\n```"

def main():
    """
    Main function to generate and save the HSE report.
    """
    logger.info("🚀 Starting HSE News Automation v2.0")
    
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        logger.error("❌ Critical: GEMINI_API_KEY environment variable is not set. Aborting.")
        sys.exit(1)
        
    report_content = get_hse_briefing(api_key)
    
    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(exist_ok=True)
    report_file = output_path / "latest_report.md"
    
    try:
        report_file.write_text(report_content, encoding='utf-8')
        logger.info(f"✅ Report successfully saved to {report_file}")
    except Exception as e:
        logger.error(f"❌ Failed to write report to file: {e}")
        sys.exit(1)
        
    logger.info("🎉 Process completed.")
    sys.exit(0)

if __name__ == '__main__':
    main()
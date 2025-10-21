from modules.scrape_article import scrape_article
from bs4 import BeautifulSoup
import re
from datetime import datetime

# ✨ NEW: Helper function to clean up messy titles from the API
def clean_title(title, source_name):
    """
    Removes the source name and other common junk from the end of a title.
    Example: "Some News Event - My News Site" -> "Some News Event"
    """
    if not title:
        return ""
    # Split by ' - ' and take the first part. This is a common pattern.
    parts = title.rsplit(' - ', 1)
    cleaned = parts[0]
    # Also remove the source name if it's still there
    if source_name and cleaned.endswith(source_name):
        cleaned = cleaned[:-len(source_name)].strip()
    return cleaned.strip()

def clean_and_format_content(raw_content):
    """
    Cleans and formats raw HTML content.
    """
    soup = BeautifulSoup(raw_content, "html.parser")
    text = soup.get_text(separator="\n")
    paragraphs = [re.sub(r'\s+', ' ', para).strip() for para in text.splitlines() if para.strip()]
    formatted_text = "\n\n".join(paragraphs)
    return formatted_text

def fetch_full_content(api_response):
    """
    For each article, scrape content, clean it, and format dates.
    NOW also cleans the article title.
    """
    for article in api_response.get('articles', []):
        # ... (content scraping remains the same)
        url = article.get('url')
        if url:
            try:
                raw_content = scrape_article(url)
                article['content'] = clean_and_format_content(raw_content)
            except Exception:
                article['content'] = None
        else:
            article['content'] = None
            
        # ✨ NEW: Clean the title before sending it to the frontend
        original_title = article.get('title', '')
        source_name = article.get('source', {}).get('name', '')
        article['title'] = clean_title(original_title, source_name)

        # ... (publishedAt date processing remains the same)
        published_at = article.get('publishedAt')
        if published_at:
            try:
                dt = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ")
                article['published_date'] = dt.strftime("%Y-%m-%d")
                article['published_time'] = dt.strftime("%H:%M:%S")
            except Exception:
                article['published_date'] = published_at
                article['published_time'] = ""
        else:
            article['published_date'] = ""
            article['published_time'] = ""
            
    return api_response
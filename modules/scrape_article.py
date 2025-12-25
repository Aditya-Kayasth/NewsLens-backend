import logging
from datetime import timedelta
from bs4 import BeautifulSoup
import requests

from cache import r

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.0.0 Safari/537.36"
    )
}

def scrape_article(url, use_cache=True):
    cache_key = f"article_cache:{url}"
    
    if use_cache:
        try:
            cached_content = r.get(cache_key)
            if cached_content:
                logger.info(f"Cache hit for: {url}")
                return cached_content.decode('utf-8')
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            
    try:
        logger.info(f"Scraping article: {url}")
        
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "html.parser")
        
        for tag in soup(['script', 'style', 'nav', 'footer', 'aside', 'header', 'iframe']):
            tag.decompose()
        
        selectors = [
            'article',
            {'class': ['article-content', 'post-content', 'entry-content', 'content', 'article-body']},
            {'id': ['article', 'content', 'main-content']}
        ]
        
        article_content = None
        for selector in selectors:
            if isinstance(selector, str):
                article_content = soup.find(selector)
            else:
                article_content = soup.find('div', selector)
            if article_content:
                break
        
        if article_content:
            paragraphs = article_content.find_all("p")
        else:
            paragraphs = soup.find_all("p")
        
        article_text = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        
        if article_text and use_cache:
            try:
                r.setex(cache_key, timedelta(hours=24), article_text)
                logger.info(f"Cached article: {url}")
            except Exception as e:
                logger.error(f"Redis set error: {e}")
        
        return article_text.strip() if article_text else ""
    
    except requests.exceptions.Timeout:
        logger.error(f"Timeout scraping article: {url}")
        return ""
    except requests.exceptions.RequestException as e:
        logger.error(f"Error scraping article at {url}: {e}")
        return ""
    except Exception as e:
        logger.error(f"Unexpected error scraping {url}: {e}")
        return ""
import logging
import os
import json
import hashlib
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.0.0 Safari/537.36"
    )
}

# Cache directory
CACHE_DIR = "data/cache"
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

def get_cache_key(url):
    """Generate cache key from URL"""
    return hashlib.md5(url.encode()).hexdigest()

def get_cached_article(url, max_age_hours=24):
    """
    Get cached article if it exists and is not expired
    
    Args:
        url (str): Article URL
        max_age_hours (int): Maximum age of cache in hours
        
    Returns:
        str or None: Cached article text or None if not found/expired
    """
    cache_key = get_cache_key(url)
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                cached_time = datetime.fromisoformat(data['cached_at'])
                
                # Check if cache is still valid
                if datetime.now() - cached_time < timedelta(hours=max_age_hours):
                    logger.info(f"Cache hit for: {url}")
                    return data['content']
                else:
                    logger.info(f"Cache expired for: {url}")
        except Exception as e:
            logger.error(f"Error reading cache: {e}")
    
    return None

def save_to_cache(url, content):
    """
    Save article content to cache
    
    Args:
        url (str): Article URL
        content (str): Article content
    """
    cache_key = get_cache_key(url)
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    
    try:
        data = {
            'url': url,
            'content': content,
            'cached_at': datetime.now().isoformat()
        }
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Cached article: {url}")
    except Exception as e:
        logger.error(f"Error saving to cache: {e}")

def scrape_article(url, use_cache=True):
    """
    Given an article URL, fetch and return the article content.
    Uses caching to avoid repeated requests.
    
    Args:
        url (str): Article URL
        use_cache (bool): Whether to use caching
        
    Returns:
        str: Article text content
    """
    # Check cache first
    if use_cache:
        cached_content = get_cached_article(url)
        if cached_content:
            return cached_content
    
    try:
        logger.info(f"Scraping article: {url}")
        
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Remove unwanted elements
        for tag in soup(['script', 'style', 'nav', 'footer', 'aside', 'header', 'iframe']):
            tag.decompose()
        
        # Try to find article content
        article_content = None
        
        # Try common article selectors
        selectors = [
            'article',
            {'class': ['article-content', 'post-content', 'entry-content', 'content', 'article-body']},
            {'id': ['article', 'content', 'main-content']}
        ]
        
        for selector in selectors:
            if isinstance(selector, str):
                article_content = soup.find(selector)
            else:
                article_content = soup.find('div', selector)
            
            if article_content:
                break
        
        # If no article container found, get all paragraphs
        if article_content:
            paragraphs = article_content.find_all("p")
        else:
            paragraphs = soup.find_all("p")
        
        # Extract text from paragraphs
        article_text = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        
        # Save to cache if content was found
        if article_text and use_cache:
            save_to_cache(url, article_text)
        
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

def clear_cache():
    """Clear all cached articles"""
    try:
        for file in os.listdir(CACHE_DIR):
            file_path = os.path.join(CACHE_DIR, file)
            if os.path.isfile(file_path):
                os.unlink(file_path)
        logger.info("Cache cleared successfully")
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
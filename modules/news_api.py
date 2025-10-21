import os
import requests
from dotenv import load_dotenv

load_dotenv()

NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
BASE_URL = "https://newsapi.org/v2"

def get_articles(params):
    """
    Fetch news articles from NewsAPI
    
    Args:
        params (dict): Query parameters for the API
        
    Returns:
        dict: API response with articles
    """
    try:
        response = requests.get(
            f"{BASE_URL}/everything",
            params=params,
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "message": "Request timed out",
            "articles": []
        }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "message": str(e),
            "articles": []
        }

def top_headlines(params):
    """
    Fetch top headlines from NewsAPI
    
    Args:
        params (dict): Query parameters for the API
        
    Returns:
        dict: API response with top headlines
    """
    try:
        response = requests.get(
            f"{BASE_URL}/top-headlines",
            params=params,
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "message": "Request timed out",
            "articles": []
        }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "message": str(e),
            "articles": []
        }
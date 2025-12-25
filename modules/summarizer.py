import os
import google.generativeai as genai
from flask import jsonify
from datetime import datetime, timedelta

from modules.scrape_article import scrape_article
from modules.news_api import get_articles
from modules.content import clean_and_format_content

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables!")

genai.configure(api_key=GEMINI_API_KEY)

def related_articles_content(article_url, NEWSAPI_KEY):
    original_content = scrape_article(article_url)
    if not original_content:
        return None, None, None

    from_date = (datetime.utcnow() - timedelta(days=2)).strftime('%Y-%m-%d')
    params = {
        'q': ' '.join(original_content.split()[:50]),
        'from': from_date,
        'language': 'en',
        'sortBy': 'relevancy',
        'pageSize': 5,
        'apiKey': NEWSAPI_KEY
    }
    related_articles_api_response = get_articles(params)
    related_articles = related_articles_api_response.get('articles', [])

    docs = []
    info = []
    for article in related_articles:
        url = article.get('url')
        title = article.get('title')
        content = scrape_article(url)
        if content:
            formatted_content = clean_and_format_content(content)
            if formatted_content:
                docs.append(formatted_content)
                info.append({'title': title, 'url': url})

    if not docs:
        docs.append(original_content)

    return docs, None, info

def gemini_summarizer(docs, info=None):
    if not docs:
        return jsonify({"error": "No content available to summarize."})

    all_text = '\n\n'.join(docs)
    
    prompt = f"""These are some news articles. Your job is to extract the factual data from these without changing any context; just present facts in a short 4-5 line professional summary.

Articles:
{all_text}"""

    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)
        summary = response.text
    except Exception as e:
        return jsonify({"error": f"Summarization failed: {str(e)}"})

    summary_data = {
        'articles': [{
            'title': 'Summary',
            'description': summary,
            'info': info if info else []
        }]
    }
    
    return jsonify(summary_data)
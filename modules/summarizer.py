import os
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from flask import jsonify
import json
from datetime import datetime, timedelta

from modules.scrape_article import scrape_article
from modules.news_api import get_articles
from modules.content import clean_and_format_content

# Download NLTK resources if not already present
nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)

def extract_keywords(text, num_keywords=5):
    """Extract keywords from text using frequency analysis"""
    words = word_tokenize(text.lower())
    words = [word for word in words if word.isalpha()]
    stop_words = set(stopwords.words('english'))
    filtered_words = [word for word in words if word not in stop_words]
    freq = nltk.FreqDist(filtered_words)
    most_common = freq.most_common(num_keywords)
    keywords = [word for word, _ in most_common]
    print(f"Extracted Keywords: {keywords}")
    return keywords

def related_articles_content(article_url, NEWSAPI_KEY):
    """
    Scrapes a main article, finds related articles, and returns their content.
    **NEW:** If no related articles are found, it falls back to the main article's content.
    """
    # 1. Scrape the original article first. This is our fallback.
    original_content = scrape_article(article_url)
    if not original_content:
        return None, None, None

    # 2. Try to find related articles based on keywords
    keywords = extract_keywords(original_content)
    query = ' '.join(keywords)
    print(f"Search Query: {query}")
    from_date = (datetime.utcnow() - timedelta(days=2)).strftime('%Y-%m-%d')
    params = {
        'q': query, 'from': from_date, 'language': 'en', 'sortBy': 'relevancy',
        'pageSize': 5,  # Limit to 5 to speed up scraping
        'apiKey': NEWSAPI_KEY
    }
    related_articles_api_response = get_articles(params)
    related_articles = related_articles_api_response.get('articles', [])
    print(f"Number of related articles found: {len(related_articles)}")

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

    # 3. FALLBACK LOGIC
    # If after all that, docs is still empty, use the original article.
    if not docs:
        print("Fallback: No related articles found or scraped. Using original article for summary.")
        docs.append(original_content)
        # We don't have a title for the 'info' here, but that's okay.
        # The summary will still work.

    print(f"Number of documents for summarization: {len(docs)}")
    return docs, query, info

def simple_summarizer(docs, query=None, summary_length=6, info=None):
    """
    Simple extractive summarizer. (No changes needed here, but included for completeness)
    """
    if not docs:
        return jsonify({ "error": "No content available to summarize." })

    all_text = ' '.join(docs)
    sentences = sent_tokenize(all_text)
    
    if not sentences:
        return jsonify({ "error": "No sentences found in content." })

    if query:
        keywords = set(query.lower().split())
    else:
        keywords = set(extract_keywords(all_text, num_keywords=10))

    sentence_scores = {i: sum(1 for word in word_tokenize(sentence.lower()) if word in keywords) for i, sentence in enumerate(sentences)}
    
    # Filter out sentences with no keyword matches unless none have matches
    scored_indices = {i: score for i, score in sentence_scores.items() if score > 0}
    if not scored_indices:
        top_indices = list(range(min(summary_length, len(sentences))))
    else:
        top_indices = sorted(scored_indices, key=scored_indices.get, reverse=True)[:summary_length]
    
    top_indices.sort()
    
    summary = ' '.join([sentences[idx] for idx in top_indices])
    
    print(f"Generated Summary: {summary[:200]}...")

    summary_data = {
        'articles': [{
            'title': 'Summary',
            'description': summary,
            'info': info if info else []
        }]
    }
    return jsonify(summary_data)

# Alias for backward compatibility
def mmr_summarizer(docs, query=None, lambda_param=0.5, summary_length=6, related=None, info=None):
    return simple_summarizer(docs, query, summary_length, info)
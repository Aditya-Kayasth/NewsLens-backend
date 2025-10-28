import os
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from flask import jsonify
import json
from datetime import datetime, timedelta

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from modules.scrape_article import scrape_article
from modules.news_api import get_articles
from modules.content import clean_and_format_content

# Download NLTK resources if not already present
nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)

def extract_keywords(text, num_keywords=5):
    """Extract keywords from text using frequency analysis"""
    # This function is unchanged
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
    # This function is unchanged
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
    Simple extractive summarizer. (This function is unchanged and used as a fallback)
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

def mmr_summarizer(docs, query=None, lambda_param=0.5, summary_length=6, info=None):
    """
    Generates an extractive summary using the Maximal Marginal Relevance (MMR) algorithm.
    This balances relevance to the query with the novelty of the information.
    """
    # Note: The 'related=None' param from your placeholder is removed as app.py doesn't use it.
    # The signature now matches the one in the editor.
    
    if not docs:
        return jsonify({"error": "No content available to summarize."})

    # Combine all documents and split into sentences
    all_text = ' '.join(docs)
    sentences = sent_tokenize(all_text)
    
    if not sentences:
        return jsonify({"error": "No sentences found in content."})
    
    # Ensure summary length is not greater than the number of sentences
    summary_length = min(summary_length, len(sentences))

    # Fallback for query: if no query is provided, use keywords from the text
    if not query:
        query = ' '.join(extract_keywords(all_text, num_keywords=10))
        print(f"MMR: No query provided, using extracted keywords: {query}")
        
    # --- TF-IDF and Similarity Calculation ---
    try:
        # Initialize the vectorizer
        stop_words = list(stopwords.words('english'))
        vectorizer = TfidfVectorizer(stop_words=stop_words)

        # Create TF-IDF matrix for all sentences
        sentence_vectors = vectorizer.fit_transform(sentences)
        
        # Create TF-IDF vector for the query
        query_vector = vectorizer.transform([query])
        
        # 1. Calculate Relevance (Sim_1): Similarity of each sentence to the query
        relevance_scores = cosine_similarity(sentence_vectors, query_vector).flatten()
        
        # 2. Calculate Redundancy (Sim_2): Similarity between all sentences
        # This creates a (num_sentences x num_sentences) matrix
        sentence_similarity_matrix = cosine_similarity(sentence_vectors)
        
    except ValueError as e:
        # This can happen if all docs are empty or just contain stopwords
        print(f"TF-IDF Error: {e}. Falling back to simple summary.")
        # Fallback to the simple summarizer if TF-IDF fails
        return simple_summarizer(docs, query, summary_length, info)

    # --- MMR Algorithm ---
    
    # Get the indices of sentences, ranked by relevance
    ranked_indices = np.argsort(relevance_scores)[::-1]
    
    # Initialize lists
    selected_indices = []
    candidate_indices = list(ranked_indices)

    # 1. Add the most relevant sentence to the summary
    if not candidate_indices:
        return jsonify({"error": "No relevant sentences found for summary."})
        
    best_index = candidate_indices[0]
    selected_indices.append(best_index)
    candidate_indices.pop(0)
    
    # 2. Iteratively add the next best sentences based on MMR score
    while len(selected_indices) < summary_length and candidate_indices:
        mmr_scores = []
        
        # Calculate MMR for each remaining candidate
        for cand_idx in candidate_indices:
            # Relevance part
            relevance = lambda_param * relevance_scores[cand_idx]
            
            # Redundancy part: find max similarity to *already selected* sentences
            redundancy = (1 - lambda_param) * max(
                sentence_similarity_matrix[cand_idx][sel_idx] for sel_idx in selected_indices
            )
            
            mmr = relevance - redundancy
            mmr_scores.append((mmr, cand_idx))
            
        # Select the candidate with the highest MMR score
        if not mmr_scores:
            break # No more candidates to score
            
        best_mmr, best_idx = max(mmD_scores)
        
        # Add to summary and remove from candidates
        selected_indices.append(best_idx)
        candidate_indices.remove(best_idx)

    # Sort the selected sentences by their original order in the text
    selected_indices.sort()
    
    # Join the sentences to create the final summary
    summary = ' '.join([sentences[idx] for idx in selected_indices])
    
    print(f"Generated MMR Summary: {summary[:200]}...")

    # Return in the exact format the API expects
    summary_data = {
        'articles': [{
            'title': 'Summary',
            'description': summary,
            'info': info if info else []
        }]
    }
    
    # We use jsonify here as this function is called directly by the Flask route
    return jsonify(summary_data)


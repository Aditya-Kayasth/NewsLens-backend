from textblob import TextBlob

def analyze_sentiments(api_response):
    """
    Analyzes the sentiment of each article's content.
    **NEW:** This version sends the raw numerical scores for maximum precision.
    """
    for article in api_response.get('articles', []):
        content = article.get('content')
        
        # If content exists, perform the analysis
        if content and isinstance(content, str) and len(content) > 50:
            try:
                blob = TextBlob(content)
                # Directly attach the raw float scores
                article['sentiment'] = {
                    'raw_polarity': blob.sentiment.polarity,       # e.g., -0.25
                    'raw_subjectivity': blob.sentiment.subjectivity # e.g., 0.68
                }
            except Exception:
                # Fallback if TextBlob fails
                article['sentiment'] = None
        else:
            # If no content, set sentiment to None
            article['sentiment'] = None
            
    return api_response
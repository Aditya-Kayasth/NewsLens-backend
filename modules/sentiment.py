from textblob import TextBlob

def analyze_sentiments(api_response):
    for article in api_response.get('articles', []):
        content = article.get('content')
        
        if content and isinstance(content, str) and len(content) > 50:
            try:
                blob = TextBlob(content)
                article['sentiment'] = {
                    'raw_polarity': blob.sentiment.polarity,
                    'raw_subjectivity': blob.sentiment.subjectivity
                }
            except Exception:
                article['sentiment'] = None
        else:
            article['sentiment'] = None
            
    return api_response
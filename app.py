import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta

import jwt
import bcrypt
import nltk

from modules.news_api import get_articles, top_headlines
from modules.content import fetch_full_content
from modules.sentiment import analyze_sentiments
from modules.summarizer import related_articles_content, gemini_summarizer

from models import db, User
from cache import r

nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment variables!")
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
CORS(app, resources={
    r"/*": {
        "origins": [FRONTEND_URL, "http://192.168.55.182:3000"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key_here")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")

if not NEWSAPI_KEY:
    raise ValueError("NEWSAPI_KEY not found in environment variables!")

@app.route("/signup", methods=["POST", "OPTIONS"])
def signup():
    if request.method == "OPTIONS":
        return jsonify({"message": "CORS preflight"}), 200
    data = request.get_json()
    if not all(k in data for k in ("name", "email", "password", "location")):
        return jsonify({"error": "Missing required fields"}), 400
    
    existing_user = User.query.filter_by(email=data["email"]).first()
    if existing_user:
        return jsonify({"error": "User already exists"}), 400
    
    hashed_pw = bcrypt.hashpw(data["password"].encode(), bcrypt.gensalt()).decode()
    
    new_user = User(
        name=data["name"],
        email=data["email"],
        password=hashed_pw,
        location=data["location"],
        preferred_domains=[]
    )
    
    try:
        db.session.add(new_user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Database error: {str(e)}"}), 500

    return jsonify({"message": "User registered successfully", "redirect": "/preferences"}), 201

@app.route("/login", methods=["POST", "OPTIONS"])
def login():
    if request.method == "OPTIONS":
        return jsonify({"message": "CORS preflight"}), 200
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400
    
    user = User.query.filter_by(email=email).first()
    
    if not user or not bcrypt.checkpw(password.encode(), user.password.encode()):
        return jsonify({"error": "Invalid credentials"}), 401
    
    token = jwt.encode({"email": email, "exp": datetime.utcnow() + timedelta(hours=24)}, SECRET_KEY, algorithm="HS256")
    
    return jsonify({
        "token": token,
        "redirect": "/news-home",
        "user": user.as_dict()
    }), 200

@app.route("/update_preferences", methods=["POST", "OPTIONS"])
def update_preferences():
    if request.method == "OPTIONS":
        return jsonify({"message": "CORS preflight"}), 200
    data = request.get_json()
    email = data.get("email")
    preferences = data.get("preferred_domains", [])
    if not email:
        return jsonify({"error": "Email required"}), 400
    
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    try:
        user.preferred_domains = preferences
        db.session.commit()
        return jsonify({"message": "Preferences updated successfully!"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Database error: {str(e)}"}), 500

@app.route("/get_preferences", methods=["POST"])
def get_preferences():
    data = request.get_json()
    email = data.get("email")
    if not email:
        return jsonify({"error": "Email required"}), 400
        
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    return jsonify({"preferred_domains": user.preferred_domains or []}), 200

@app.route("/news", methods=["POST", "OPTIONS"])
def fetch_news():
    if request.method == "OPTIONS":
        return jsonify({"message": "CORS preflight"}), 200
    
    data = request.get_json()
    email = data.get("email")
    page = data.get("page", 1)
    category = data.get("category")

    if not email:
        return jsonify({"error": "Email required"}), 400

    query = ''
    if category:
        query = category
    else:
        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        topics = user.preferred_domains
        if not topics or len(topics) == 0:
            return jsonify({"articles": [], "totalResults": 0, "page": page}), 200
        query = ' OR '.join(topics)

    from_date = (datetime.utcnow() - timedelta(days=3)).strftime('%Y-%m-%d')
    params = {'q': query, 'from': from_date, 'language': 'en', 'sortBy': 'relevancy', 'page': page, 'pageSize': 20, 'apiKey': NEWSAPI_KEY}

    try:
        api_response = get_articles(params)
        if api_response.get('status') != 'ok':
            return jsonify({"error": "Failed to fetch news", "details": api_response.get('message', 'Unknown')}), 500
        
        api_response = fetch_full_content(api_response)
        api_response = analyze_sentiments(api_response)
        api_response['articles'] = [a for a in api_response.get('articles', []) if a.get('content') and a.get('urlToImage')]

        return jsonify({"articles": api_response.get('articles', []), "totalResults": api_response.get('totalResults', 0), "page": page}), 200
    
    except Exception as e:
        return jsonify({"error": f"Error fetching news: {str(e)}"}), 500

@app.route("/top-headlines", methods=["POST", "OPTIONS"])
def fetch_top_headlines():
    if request.method == "OPTIONS":
        return jsonify({"message": "CORS preflight"}), 200
    
    data = request.get_json()
    page = data.get("page", 1)
    
    params = {'country': 'us', 'page': page, 'pageSize': 20, 'apiKey': NEWSAPI_KEY}
    
    try:
        api_response = top_headlines(params)
        if api_response.get('status') != 'ok':
            return jsonify({"error": "Failed to fetch top headlines", "details": api_response.get('message', 'Unknown')}), 500
        
        api_response = fetch_full_content(api_response)
        api_response = analyze_sentiments(api_response)
        api_response['articles'] = [a for a in api_response.get('articles', []) if a.get('content') and a.get('urlToImage')]
        
        return jsonify({"articles": api_response.get('articles', []), "totalResults": api_response.get('totalResults', 0), "page": page}), 200
    
    except Exception as e:
        return jsonify({"error": f"Error fetching top headlines: {str(e)}"}), 500

@app.route("/search", methods=["POST", "OPTIONS"])
def search():
    if request.method == "OPTIONS":
        return jsonify({"message": "CORS preflight"}), 200
    data = request.get_json()
    query = data.get('query', '')
    page = data.get('page', 1)
    if not query:
        return jsonify({"error": "Search query is required"}), 400
    from_date = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')
    params = {'q': query, 'from': from_date, 'language': 'en', 'sortBy': 'relevancy', 'page': page, 'pageSize': 20, 'apiKey': NEWSAPI_KEY}

    try:
        api_response = get_articles(params)
        if api_response.get('status') != 'ok':
            return jsonify({"error": "Search failed"}), 500
        
        api_response = fetch_full_content(api_response)
        api_response = analyze_sentiments(api_response)
        api_response['articles'] = [a for a in api_response.get('articles', []) if a.get('content') and a.get('urlToImage')]
        
        return jsonify({"articles": api_response.get('articles', []), "totalResults": api_response.get('totalResults', 0), "page": page}), 200
    except Exception as e:
        return jsonify({"error": f"Search error: {str(e)}"}), 500

@app.route("/summarize", methods=["POST", "OPTIONS"])
def summarize():
    if request.method == "OPTIONS":
        return jsonify({"message": "CORS preflight"}), 200
    data = request.get_json()
    article_url = data.get('article_url')
    if not article_url:
        return jsonify({"error": "Article URL is required"}), 400
    try:
        docs, query, info = related_articles_content(article_url, NEWSAPI_KEY)
        if not docs:
            return jsonify({"error": "Could not retrieve content for summarization"}), 404
        summary = gemini_summarizer(docs, info=info)
        return summary
    except Exception as e:
        return jsonify({"error": f"Summarization failed: {str(e)}"}), 500

@app.route("/health", methods=["GET"])
def health():
    db_status = "disconnected"
    redis_status = "disconnected"
    
    try:
        db.session.execute(db.text('SELECT 1'))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    try:
        r.ping()
        redis_status = "connected"
    except Exception as e:
        redis_status = f"error: {str(e)}"

    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": db_status,
        "cache": redis_status
    }), 200

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    app.run(debug=True, host='0.0.0.0', port=5000)
import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.exceptions import HTTPException
import logging
from logging.handlers import RotatingFileHandler

import jwt
import bcrypt
import nltk

from modules.news_api import get_articles, top_headlines
from modules.content import fetch_full_content
from modules.sentiment import analyze_sentiments
from modules.summarizer import related_articles_content, mmr_summarizer

from models import db, User
from cache import r

nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)

app = Flask(__name__)

# Database Config
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment variables!")
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Rate Limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=os.getenv("REDIS_URL")
)

# CORS
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
CORS(app, resources={
    r"/*": {
        "origins": [FRONTEND_URL, "http://192.168.55.182:3000"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Config
SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key_here")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")

if not NEWSAPI_KEY:
    raise ValueError("NEWSAPI_KEY not found in environment variables!")

# Logging Setup
if not app.debug:
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/newslens.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('NewsLens startup')

# JWT Middleware
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        try:
            token = token.split()[1] if ' ' in token else token
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            current_user = User.query.filter_by(email=data['email']).first()
            if not current_user:
                return jsonify({'error': 'Invalid token'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except Exception:
            return jsonify({'error': 'Token is invalid'}), 401
        return f(current_user, *args, **kwargs)
    return decorated

# Request Logging
@app.before_request
def log_request():
    app.logger.info(f"{request.method} {request.path} - {request.remote_addr}")

# ==================== AUTHENTICATION ====================

@app.route("/signup", methods=["POST", "OPTIONS"])
@limiter.limit("10 per hour")
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
        app.logger.error(f"Signup error: {str(e)}")
        return jsonify({"error": "Database error occurred"}), 500

    return jsonify({"message": "User registered successfully", "redirect": "/preferences"}), 201

@app.route("/login", methods=["POST", "OPTIONS"])
@limiter.limit("5 per minute")
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
    
    token = jwt.encode(
        {"email": email, "exp": datetime.utcnow() + timedelta(hours=24)}, 
        SECRET_KEY, 
        algorithm="HS256"
    )
    
    return jsonify({ 
        "token": token, 
        "redirect": "/news-home", 
        "user": user.as_dict()
    }), 200

# ==================== PREFERENCES ====================

@app.route("/update_preferences", methods=["POST", "OPTIONS"])
@token_required
def update_preferences(current_user):
    if request.method == "OPTIONS":
        return jsonify({"message": "CORS preflight"}), 200
    
    data = request.get_json()
    preferences = data.get("preferred_domains", [])
        
    try:
        current_user.preferred_domains = preferences
        db.session.commit()
        return jsonify({"message": "Preferences updated successfully!"}), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Update preferences error: {str(e)}")
        return jsonify({"error": "Database error occurred"}), 500

@app.route("/get_preferences", methods=["POST"])
@token_required
def get_preferences(current_user):
    return jsonify({"preferred_domains": current_user.preferred_domains or []}), 200

# ==================== NEWS ====================

@app.route("/news", methods=["POST", "OPTIONS"])
@token_required
def fetch_news(current_user):
    if request.method == "OPTIONS":
        return jsonify({"message": "CORS preflight"}), 200
    
    data = request.get_json()
    page = data.get("page", 1)
    category = data.get("category")

    query = ''
    if category:
        query = category
    else:
        topics = current_user.preferred_domains
        if not topics:
            return jsonify({"error": "Please select topics in preferences"}), 400
        query = ' OR '.join(topics)

    from_date = (datetime.utcnow() - timedelta(days=3)).strftime('%Y-%m-%d')
    params = {
        'q': query, 
        'from': from_date, 
        'language': 'en', 
        'sortBy': 'relevancy', 
        'page': page, 
        'pageSize': 20, 
        'apiKey': NEWSAPI_KEY
    }

    try:
        api_response = get_articles(params)
        if api_response.get('status') != 'ok':
            return jsonify({"error": "Failed to fetch news", "details": api_response.get('message', 'Unknown')}), 500
        
        api_response = fetch_full_content(api_response)
        api_response = analyze_sentiments(api_response)
        api_response['articles'] = [
            a for a in api_response.get('articles', []) 
            if a.get('content') and a.get('urlToImage')
        ]

        return jsonify({
            "articles": api_response.get('articles', []), 
            "totalResults": api_response.get('totalResults', 0), 
            "page": page
        }), 200
    
    except Exception as e:
        app.logger.error(f"Fetch news error: {str(e)}")
        return jsonify({"error": "Error fetching news"}), 500

@app.route("/top-headlines", methods=["POST", "OPTIONS"])
def fetch_top_headlines():
    if request.method == "OPTIONS":
        return jsonify({"message": "CORS preflight"}), 200
    
    data = request.get_json()
    page = data.get("page", 1)
    
    params = {
        'country': 'us',
        'pageSize': 20,
        'page': page,
        'apiKey': NEWSAPI_KEY
    }
    
    try:
        api_response = top_headlines(params)
        if api_response.get('status') != 'ok':
            return jsonify({"error": "Failed to fetch headlines"}), 500
        
        api_response = fetch_full_content(api_response)
        api_response = analyze_sentiments(api_response)
        api_response['articles'] = [
            a for a in api_response.get('articles', []) 
            if a.get('content') and a.get('urlToImage')
        ]
        
        return jsonify({
            "articles": api_response.get('articles', []),
            "totalResults": api_response.get('totalResults', 0),
            "page": page
        }), 200
        
    except Exception as e:
        app.logger.error(f"Fetch headlines error: {str(e)}")
        return jsonify({"error": "Error fetching headlines"}), 500

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
    params = {
        'q': query, 
        'from': from_date, 
        'language': 'en', 
        'sortBy': 'relevancy', 
        'page': page, 
        'pageSize': 20, 
        'apiKey': NEWSAPI_KEY
    }

    try:
        api_response = get_articles(params)
        if api_response.get('status') != 'ok':
            return jsonify({"error": "Search failed"}), 500
        
        api_response = fetch_full_content(api_response)
        api_response = analyze_sentiments(api_response)
        api_response['articles'] = [
            a for a in api_response.get('articles', []) 
            if a.get('content') and a.get('urlToImage')
        ]
        
        return jsonify({
            "articles": api_response.get('articles', []), 
            "totalResults": api_response.get('totalResults', 0), 
            "page": page
        }), 200
    except Exception as e:
        app.logger.error(f"Search error: {str(e)}")
        return jsonify({"error": "Search error occurred"}), 500

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
        summary = mmr_summarizer(docs, query=query, summary_length=5, info=info)
        return summary
    except Exception as e:
        app.logger.error(f"Summarization error: {str(e)}")
        return jsonify({"error": "Summarization failed"}), 500

# ==================== HEALTH & ERRORS ====================

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

@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException):
        return jsonify({"error": e.description}), e.code
    
    app.logger.error(f"Unhandled exception: {str(e)}")
    return jsonify({"error": "Internal server error occurred"}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("Database tables created.")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import jwt
import bcrypt
import json
import nltk
from dotenv import load_dotenv

# Import modules
from modules.news_api import get_articles, top_headlines
from modules.content import fetch_full_content
from modules.sentiment import analyze_sentiments
from modules.summarizer import related_articles_content, mmr_summarizer

# Load environment variables
load_dotenv()

# Download NLTK data
nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)

# Initialize Flask app
app = Flask(__name__)

# Configure CORS
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
CORS(app, resources={
    r"/*": {
        "origins": [FRONTEND_URL, "http://192.168.55.182:3000"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Configuration
USERS_FILE = "data/users.json"
SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key_here")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")

if not NEWSAPI_KEY:
    raise ValueError("NEWSAPI_KEY not found in environment variables!")

if not os.path.exists("data"):
    os.makedirs("data")

# Helper functions
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return {"users": []}
    return {"users": []}

def save_users(users):
    with open(USERS_FILE, "w") as file:
        json.dump(users, file, indent=2)

# ==================== AUTHENTICATION ROUTES ====================

@app.route("/signup", methods=["POST", "OPTIONS"])
def signup():
    if request.method == "OPTIONS":
        return jsonify({"message": "CORS preflight"}), 200
    data = request.get_json()
    if not all(k in data for k in ("name", "email", "password", "location")):
        return jsonify({"error": "Missing required fields"}), 400
    users = load_users()
    if any(user["email"] == data["email"] for user in users["users"]):
        return jsonify({"error": "User already exists"}), 400
    hashed_pw = bcrypt.hashpw(data["password"].encode(), bcrypt.gensalt()).decode()
    new_user = { "name": data["name"], "email": data["email"], "password": hashed_pw, "location": data["location"], "preferred_domains": [] }
    users["users"].append(new_user)
    save_users(users)
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
    users = load_users()
    user = next((u for u in users["users"] if u["email"] == email), None)
    if not user or not bcrypt.checkpw(password.encode(), user["password"].encode()):
        return jsonify({"error": "Invalid credentials"}), 401
    token = jwt.encode( {"email": email, "exp": datetime.utcnow() + timedelta(hours=24)}, SECRET_KEY, algorithm="HS256" )
    return jsonify({ "token": token, "redirect": "/news-home", "user": { "name": user["name"], "email": user["email"], "preferred_domains": user.get("preferred_domains", []) } }), 200

# ==================== PREFERENCES ROUTES ====================

@app.route("/update_preferences", methods=["POST", "OPTIONS"])
def update_preferences():
    if request.method == "OPTIONS":
        return jsonify({"message": "CORS preflight"}), 200
    data = request.get_json()
    email = data.get("email")
    preferences = data.get("preferred_domains", [])
    if not email:
        return jsonify({"error": "Email required"}), 400
    users = load_users()
    for user in users["users"]:
        if user["email"] == email:
            user["preferred_domains"] = preferences
            save_users(users)
            return jsonify({"message": "Preferences updated successfully!"}), 200
    return jsonify({"error": "User not found"}), 404

# ✨ NEW ROUTE to get user's saved preferences
@app.route("/get_preferences", methods=["POST"])
def get_preferences():
    data = request.get_json()
    email = data.get("email")
    if not email:
        return jsonify({"error": "Email required"}), 400
    users = load_users()
    user = next((u for u in users["users"] if u["email"] == email), None)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"preferred_domains": user.get("preferred_domains", [])}), 200


# ==================== NEWS ROUTES ====================

# ✨ MODIFIED ROUTE to handle general feed and specific categories
@app.route("/news", methods=["POST", "OPTIONS"])
def fetch_news():
    if request.method == "OPTIONS":
        return jsonify({"message": "CORS preflight"}), 200
    
    data = request.get_json()
    email = data.get("email")
    page = data.get("page", 1)
    category = data.get("category")  # Look for a specific category

    if not email:
        return jsonify({"error": "Email required"}), 400

    query = ''
    if category:
        query = category
    else:
        users = load_users()
        user = next((u for u in users["users"] if u["email"] == email), None)
        if not user: return jsonify({"error": "User not found"}), 404
        topics = user.get("preferred_domains", [])
        if not topics: return jsonify({"error": "Please select topics in preferences"}), 400
        query = ' OR '.join(topics)

    from_date = (datetime.utcnow() - timedelta(days=3)).strftime('%Y-%m-%d')
    params = {'q': query, 'from': from_date, 'language': 'en', 'sortBy': 'relevancy', 'page': page, 'pageSize': 20, 'apiKey': NEWSAPI_KEY}

    try:
        api_response = get_articles(params)
        if api_response.get('status') != 'ok':
            return jsonify({"error": "Failed to fetch news", "details": api_response.get('message', 'Unknown')}), 500
        
        api_response = fetch_full_content(api_response)
        api_response = analyze_sentiments(api_response)

        # Filter out articles that failed to scrape
        api_response['articles'] = [article for article in api_response.get('articles', []) if article.get('content')]
        # ✨ NEW: Filter out articles that DO NOT have an image
        api_response['articles'] = [article for article in api_response.get('articles', []) if article.get('urlToImage')]

        return jsonify({"articles": api_response.get('articles', []), "totalResults": api_response.get('totalResults', 0), "page": page}), 200
    
    except Exception as e:
        return jsonify({"error": f"Error fetching news: {str(e)}"}), 500

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
        # Apply filters here as well
        api_response['articles'] = [a for a in api_response.get('articles', []) if a.get('content') and a.get('urlToImage')]
        
        return jsonify({"articles": api_response.get('articles', []), "totalResults": api_response.get('totalResults', 0), "page": page}), 200
    except Exception as e:
        return jsonify({"error": f"Search error: {str(e)}"}), 500


# ==================== SUMMARIZATION AND OTHER ROUTES ====================

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
        return jsonify({"error": f"Summarization failed: {str(e)}"}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()}), 200

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
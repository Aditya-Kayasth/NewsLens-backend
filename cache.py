# cache.py
import os
import redis
from dotenv import load_dotenv

load_dotenv() # Load .env variables

# 1. Get the single URL from the .env file
REDIS_URL = os.getenv("REDIS_URL")

if not REDIS_URL:
    raise ValueError("REDIS_URL must be set in your .env file")

# 2. Connect using the from_url() method
try:
    r = redis.Redis.from_url(REDIS_URL)
    r.ping() # Test the connection
    print("Connected to Redis at Upstash.")
except Exception as e:
    print(f"Failed to connect to Redis: {e}")
    raise
# NewsLens Backend

NewsLens is a full-stack news aggregation and analysis platform. This repository contains the **RESTful API** built with Flask, which handles data aggregation, NLP processing, and generative AI summarization.

**[Live Demo](https://news-lens-project.vercel.app) | [Frontend Repository](https://github.com/Aditya-Kayasth/NewsLens-frontend)**

## Key Features

* **API Endpoints:** RESTful architecture serving news data, user preferences, and authentication.
* **Generative AI Summarization:** Integrated **Google Gemini 2.5 Flash** to generate concise, abstractive summaries of news articles.
* **NLP Pipeline:** Custom processing modules using NLTK and TextBlob for keyword extraction and sentiment analysis.
* **Database:** PostgreSQL with SQLAlchemy ORM for managing user data and preferences.
* **Caching:** Redis implementation to reduce external API latency.

## Tech Stack

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Flask](https://img.shields.io/badge/flask-%23000.svg?style=for-the-badge&logo=flask&logoColor=white)
![Google Gemini](https://img.shields.io/badge/Google%20Gemini-8E75B2?style=for-the-badge&logo=google%20gemini&logoColor=white)
![Postgres](https://img.shields.io/badge/postgres-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/redis-%23DD0031.svg?style=for-the-badge&logo=redis&logoColor=white)
![Render](https://img.shields.io/badge/Render-%2346E3B7.svg?style=for-the-badge&logo=render&logoColor=white)

## Local Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/yourusername/newslens-backend.git](https://github.com/yourusername/newslens-backend.git)
    cd newslens-backend
    ```

2.  **Set up virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment:**
    Create a `.env` file with the following:
    ```env
    DATABASE_URL=postgresql://user:pass@localhost/newslens
    NEWSAPI_KEY=your_newsapi_key
    GEMINI_API_KEY=your_gemini_key
    SECRET_KEY=your_secret
    FRONTEND_URL=http://localhost:3000
    REDIS_URL=redis://localhost:6379
    ```

5.  **Run the server:**
    ```bash
    python app.py
    ```

The API will be available at `http://localhost:5000`.

## Future Roadmap

* **Vector Database:** Migration to vector storage for semantic search capabilities.
* **Advanced Analytics:** User reading habits and trend visualization.

## License

MIT License.

NewsLens is a full-stack news aggregation and analysis platform. This repository contains the **RESTful API** built with Flask, which handles data aggregation, NLP processing (sentiment analysis & summarization), and database management.

**[Live Demo](https://news-lens-project.vercel.app) | [Frontend Repository](https://github.com/Aditya-Kayasth/NewsLens-frontend)**

## Key Features

* **API Endpoints:** RESTful architecture serving news data, user preferences, and authentication.
* **NLP Pipeline:** Custom processing modules using NLTK and Scikit-learn for keyword extraction and sentiment analysis.
* **Extractive Summarization:** Algorithms (TF-IDF & MMR) to condense long articles into concise summaries.
* **Database:** PostgreSQL with SQLAlchemy ORM for managing user data and preferences.
* **Caching:** Redis implementation to reduce external API latency.

## Tech Stack

* **Framework:** Flask (Python 3.10+)
* **Database:** PostgreSQL
* **Caching:** Redis
* **Libraries:** NLTK, Scikit-learn, SQLAlchemy, PyJWT, Bcrypt
* **Deployment:** Render

## Local Installation

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/yourusername/newslens-backend.git](https://github.com/yourusername/newslens-backend.git)
   cd newslens-backend

```

2. **Set up virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

```


3. **Install dependencies:**
```bash
pip install -r requirements.txt

```


4. **Configure Environment:**
Create a `.env` file with the following:
```env
DATABASE_URL=postgresql://user:pass@localhost/newslens
NEWSAPI_KEY=your_key
SECRET_KEY=your_secret
FRONTEND_URL=http://localhost:3000

```


5. **Run the server:**
```bash
python app.py

```


The API will be available at `http://localhost:5000`.

## Future Roadmap

* **LLM Integration:** Upcoming integration of Gemini 2.0 Flash for abstractive summarization.
* **Vector Database:** Migration to vector storage for semantic search capabilities.

## License

MIT License.

```

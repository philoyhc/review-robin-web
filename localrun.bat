# One-time setup
cd review-robin-web
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
Copy-Item .env.example .env
alembic upgrade head            # creates .\review_robin_web.db
uvicorn app.main:app --reload   # serves on http://127.0.0.1:8000

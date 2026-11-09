.PHONY: backend frontend backend-test-mode setup test

# Start the API on http://localhost:8000 (reads backend/.env).
backend:
	cd backend && .venv/bin/uvicorn app.asgi:app --reload --port 8000

# Start the web app on http://localhost:3000.
frontend:
	cd frontend && npm run dev

# The API with in-memory services and a mocked LLM; no Supabase or LLM keys needed.
backend-test-mode:
	cd backend && ALIBI_TEST_MODE=1 .venv/bin/uvicorn app.asgi:app --reload --port 8000

setup:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
	cd frontend && npm install

test:
	cd backend && .venv/bin/python -m pytest --cov=app --cov-report=term
	cd frontend && npm run test:coverage

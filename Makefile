.PHONY: sync run test frontend-test up down

sync:
	cd backend && uv sync

run:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8091

test:
	cd backend && uv run pytest

frontend-test:
	cd frontend && npm install && npm test

up:
	docker compose up -d --build --wait

down:
	docker compose down -v

.PHONY: up down test test-local lint format migrate

up:
	docker compose up -d --build

down:
	docker compose down

test:
	docker compose exec api pytest tests/

test-local:
	python -m pytest

lint:
	docker compose exec api ruff check .
	docker compose exec api mypy .

format:
	docker compose exec api ruff format .
	docker compose exec api black .

migrate:
	docker compose exec api alembic upgrade head

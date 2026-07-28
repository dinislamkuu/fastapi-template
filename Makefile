.PHONY: install format lint typecheck test test-integration check up down logs migrate migration docker-build

install:
	uv sync --frozen --all-groups

format:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy app tests

test:
	uv run pytest tests/unit

test-integration:
	uv run pytest tests/integration

check: lint typecheck
	uv run pytest

up:
	docker compose up --build

down:
	docker compose down --remove-orphans

logs:
	docker compose logs -f app

migrate:
	uv run alembic upgrade head

migration:
	uv run alembic revision --autogenerate -m "$(message)"

docker-build:
	docker build -t fastapi-production-template:local .

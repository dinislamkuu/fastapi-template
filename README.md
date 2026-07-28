# fastapi-production-template

## Обзор

Компактный infrastructure-oriented шаблон FastAPI для новых backend-сервисов. Он показывает production-подход к health/readiness probes, настройкам через environment, асинхронным PostgreSQL и Redis, Alembic-миграциям, JSON-логам, request ID, Docker, Compose, тестам и защитному CI.

Public pipeline builds and validates the image. Production deployment intentionally omitted because the repository is infrastructure-neutral.

## Возможности

- Python 3.12, FastAPI, Pydantic v2, Pydantic Settings.
- Async SQLAlchemy 2.x с asyncpg и Alembic.
- Redis asyncio client.
- `GET /health/live`, `GET /health/ready`, `GET /api/v1/version`.
- JSON-логи и сквозной `X-Request-ID`.
- Единый формат ошибок без stack trace и credentials в HTTP-ответах.
- Multi-stage Docker image с runtime UID/GID `10001`.
- Docker Compose с отдельным one-shot сервисом `migrate`.
- Ruff, mypy, pytest, coverage, Docker build, Trivy, Gitleaks и SBOM в CI.

## Архитектура

Приложение создаётся через `create_app()` и использует FastAPI lifespan. Lifespan создаёт SQLAlchemy engine и Redis client без обязательных startup ping, кладёт их в `app.state`, а при завершении закрывает Redis и вызывает `dispose()` у engine.

Liveness проверяет только способность процесса отвечать на HTTP. Readiness отдельно проверяет PostgreSQL, Redis и runtime-конфигурацию с короткими timeout. При ошибке readiness возвращает `503`, но не раскрывает hostnames, DSN, пароли, exception text или stack trace.

Миграции отделены от startup приложения. В Compose сервис `migrate` выполняется один раз, а `app` стартует только после успешного завершения миграций.

## Структура репозитория

```text
app/
  api/v1/
  cache/
  core/
  db/
  health/
  schemas/
migrations/
tests/
  unit/
  integration/
.github/workflows/
```

## Требования

- Python 3.12
- uv
- Docker и Docker Compose
- make опционален

## Быстрый старт

```bash
cp .env.example .env
uv sync --frozen --all-groups
docker compose up --build
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
curl http://localhost:8000/api/v1/version
```

## Переменные окружения

| Переменная | Обязательна | Назначение |
| --- | --- | --- |
| `APP_NAME` | да | Имя сервиса в логах и metadata. |
| `APP_VERSION` | нет | Версия сервиса; по умолчанию берётся из package metadata. |
| `ENVIRONMENT` | да | `development`, `test`, `staging` или `production`. |
| `LOG_LEVEL` | да | Уровень логирования. |
| `DATABASE_URL` | да | Async SQLAlchemy URL, должен быть `postgresql+asyncpg://`. |
| `REDIS_URL` | да | Redis URL, `redis://` или `rediss://`. |
| `DB_POOL_SIZE` | да | Размер SQLAlchemy pool. |
| `DB_MAX_OVERFLOW` | да | SQLAlchemy max overflow. |
| `READINESS_TIMEOUT_SECONDS` | да | Timeout каждой readiness-проверки. |
| `DOCS_ENABLED` | да | Управляет `/docs`, `/redoc` и `/openapi.json`. |
| `ALLOWED_HOSTS` | да | Список TrustedHost через запятую. Wildcard запрещён в production. |
| `BUILD_SHA` | нет | Revision образа или сборки. |

`.env.example` содержит только локальные демонстрационные значения. Не коммитьте `.env`.

## Локальный запуск без app-контейнера

Поднимите изолированные PostgreSQL и Redis на localhost-портах из `.env.example`:

```bash
docker compose -f compose.yaml -f compose.test.yaml up -d test-postgres test-redis
uv sync --frozen --all-groups
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

## Запуск через Docker Compose

```bash
docker compose up --build
docker compose logs -f app
docker compose down
```

В основном `compose.yaml` наружу публикуется только HTTP-порт приложения. PostgreSQL и Redis доступны только внутри Compose network.

## Health endpoints

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

Liveness не обращается к PostgreSQL или Redis. Readiness проверяет внешние зависимости и конфигурацию.

## Миграции базы данных

```bash
docker compose run --rm migrate
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "описание изменения"
```

Приложение никогда не запускает миграции автоматически при startup.

## Тесты

```bash
docker compose -f compose.yaml -f compose.test.yaml up -d test-postgres test-redis
uv run pytest
```

Тесты используют PostgreSQL на `localhost:55432` и Redis на `localhost:56379`. Fixture принудительно выставляет тестовые environment variables, поэтому внешние `DATABASE_URL` и `REDIS_URL` не уводят тесты в development или production БД.

## Проверка качества кода

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy app tests
```

Удобная обёртка:

```bash
make check
```

## Docker image

```bash
docker build -t fastapi-production-template:local .
docker run --rm fastapi-production-template:local id
```

Runtime image использует `python:3.12-slim`, builder stage, `uv sync --frozen`, production dependencies без dev-группы, `STOPSIGNAL SIGTERM`, exec-form Uvicorn `CMD`, healthcheck на Python standard library и non-root пользователя.

В контейнере используется один Uvicorn worker. Масштабирование предполагается количеством контейнеров на целевой платформе.

## CI pipeline

CI запускается на pull request, push в `main`, semver tags и manual dispatch. Pipeline выполняет `uv sync --frozen --all-groups`, Ruff, format check, mypy, Alembic migrations, pytest с PostgreSQL/Redis service containers, Docker build, проверку non-root пользователя, Trivy image scan, CycloneDX SBOM и Gitleaks.

Публикация образа отключена по умолчанию. Для GHCR нужно явно выставить repository variable `PUSH_IMAGE=true`. Только optional job `publish-image` получает `packages: write`.

## Security decisions

- Permissive CORS middleware не установлен.
- OpenAPI docs управляются через `DOCS_ENABLED` и должны быть выключены в production.
- Production-настройки запрещают wildcard `ALLOWED_HOSTS`.
- Request ID ограничен по длине и набору символов до попадания в логи.
- Error responses используют единый schema и не содержат stack trace или raw exception message.
- Readiness пишет технические причины в логи, но наружу возвращает только `ok` или `error`.
- Docker runtime использует `cap_drop: ALL`, `no-new-privileges`, read-only filesystem и tmpfs для `/tmp`.
- CI не использует `pull_request_target`.

## Production considerations

Nginx, TLS termination, ingress, reverse proxy, registry promotion и runtime deployment зависят от инфраструктуры и намеренно не входят в этот репозиторий.

## Намеренно не добавлено

В шаблоне нет CRUD, пользователей, authentication, JWT secret, admin panel, Celery, RabbitMQ, Kafka, Kubernetes, Terraform, Helm, Prometheus, Grafana, OpenTelemetry и fake deployment jobs.

## Troubleshooting

- `503` на readiness: проверьте логи приложения, PostgreSQL, Redis и обязательные environment variables.
- Alembic не подключается: проверьте, что `DATABASE_URL` начинается с `postgresql+asyncpg://`.
- Docker build падает на зависимостях: выполните `uv lock`, затем повторите сборку из чистого checkout.
- TrustedHost отклоняет запрос: добавьте ожидаемый hostname в `ALLOWED_HOSTS`.

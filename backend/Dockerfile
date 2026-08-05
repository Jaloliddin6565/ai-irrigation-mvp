FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_MODE=fixture

COPY pyproject.toml ./
COPY app ./app
COPY config ./config
COPY fixtures ./fixtures
COPY alembic.ini ./
COPY alembic ./alembic

RUN pip install --no-cache-dir .

EXPOSE 8000

# Apply migrations before serving — a fresh volume/container has no schema
# yet (Alembic never runs implicitly at import time; see docs/deployment.md).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

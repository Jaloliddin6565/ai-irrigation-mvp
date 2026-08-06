FROM node:22-slim AS frontend-build

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./

# Empty means same-origin API calls in the bundled pilot deployment.
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build


FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_MODE=fixture

COPY backend/pyproject.toml ./
COPY backend/app ./app
COPY backend/config ./config
COPY backend/fixtures ./fixtures
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY --from=frontend-build /frontend/dist ./frontend_dist

RUN pip install --no-cache-dir .

EXPOSE 8000

# Apply migrations before serving. Render supplies PORT; local Docker keeps
# the existing 8000 default.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

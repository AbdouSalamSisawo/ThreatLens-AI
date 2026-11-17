# ThreatLens AI - single-origin image: FastAPI serves the API and the built SPA.
#
#   docker compose build   (or: docker build -t threatlens .)
#
# The Supabase URL and publishable key are compiled into the browser bundle,
# so they are build arguments. Both are public by design - never pass a
# service-role key here.

# --- Stage 1: build the React frontend ---------------------------------------
FROM oven/bun:1 AS frontend
WORKDIR /src
COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile
COPY frontend/ ./
ARG VITE_SUPABASE_URL=""
ARG VITE_SUPABASE_PUBLISHABLE_KEY=""
RUN bun run build

# --- Stage 2: Python API + static frontend -----------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
# Model artefacts: baked in if present at build time, or mounted at runtime
# (see docker-compose.yml). The API reports "model unavailable" without them.
COPY backend/artifacts ./artifacts
COPY --from=frontend /src/dist ./static

RUN useradd --create-home --uid 10001 threatlens \
    && mkdir -p /app/data \
    && chown -R threatlens /app/data
USER threatlens

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

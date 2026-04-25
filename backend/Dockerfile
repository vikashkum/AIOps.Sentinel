FROM python:3.11-slim

WORKDIR /app

# Copy requirements first — Docker caches this layer and skips pip install
# on rebuilds when only source code changes.
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Production: no --reload. 2 uvicorn workers for concurrency.
# Keep workers=1 if you rely on in-process state (e.g. the background
# simulation ticker); increase only after migrating to shared state.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

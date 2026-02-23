FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/ ./backend/

RUN pip install --no-cache-dir ./backend

# Imports use "backend.src.xxx" — need /app on Python path
ENV PYTHONPATH=/app

CMD sh -c "alembic -c backend/alembic.ini upgrade head && uvicorn backend.src.main:app --host 0.0.0.0 --port ${PORT:-18001}"

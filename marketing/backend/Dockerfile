FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend /app/backend
COPY demo /app/demo

RUN useradd --create-home --uid 10001 anka \
    && mkdir -p /app/working/private /data \
    && chown -R anka:anka /app/working /data
USER anka

CMD ["sh", "-c", "uvicorn backend.app:app --host 0.0.0.0 --port ${PORT} --workers 1"]

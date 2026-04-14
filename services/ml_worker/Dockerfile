FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["celery", "-A", "tasks", "worker", "--loglevel=info", "-Q", "ml_queue", "--concurrency=2"]

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 ffmpeg wget && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# concurrency=1: la inferencia CNN14 usa toda la RAM disponible por proceso
CMD ["celery", "-A", "tasks", "worker", "--loglevel=info", "-Q", "ml_queue", "--concurrency=1"]

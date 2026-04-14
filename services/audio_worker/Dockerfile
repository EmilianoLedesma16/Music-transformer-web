FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# music-transformer/src is bind-mounted at /app/mt_src at runtime
ENV PYTHONPATH="/app/mt_src:/app"

CMD ["celery", "-A", "tasks", "worker", "--loglevel=info", "-Q", "audio_queue", "--concurrency=1"]

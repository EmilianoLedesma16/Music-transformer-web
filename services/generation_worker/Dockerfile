FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "setuptools<70.0.0" && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cu128

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["celery", "-A", "tasks", "worker", "--loglevel=info", "-Q", "generation_queue", "--concurrency=1"]

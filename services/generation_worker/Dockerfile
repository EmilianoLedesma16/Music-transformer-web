FROM pytorch/pytorch:2.3.0-cuda12.1-cudnn8-runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir "setuptools<70.0.0" && \
    pip install --no-cache-dir -r requirements.txt
COPY . .

# music-transformer/src se monta en /app/mt_src vía volumen
# PYTHONPATH se inyecta desde docker-compose
CMD ["celery", "-A", "tasks", "worker", "--loglevel=info", "-Q", "generation_queue", "--concurrency=1"]

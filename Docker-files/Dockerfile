FROM python:3.11-slim

LABEL maintainer="2kfi"
LABEL description="LLMSIMT Voice Pipeline - STT + LLM + TTS"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libportaudio2 \
    libsndfile1 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/bash -m appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.yaml config.py downloader.py pipeline.py ./

RUN mkdir -p /app/models /app/logs && \
    chown -R appuser:appgroup /app

RUN chmod -R 664 /app/models /app/logs || true

USER appuser

EXPOSE 8003

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8003/health', timeout=5)" || exit 1

CMD ["python", "pipeline.py"]

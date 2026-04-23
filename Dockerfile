FROM python:3.11-alpine

RUN apk add --no-cache \
    libsndfile \
    portaudio \
    ffmpeg \
    gcc \
    musl-dev \
    linux-headers

WORKDIR /app

COPY backend-requirements.txt .
RUN pip install --no-cache-dir -r backend-requirements.txt

COPY pipeline.py config.py downloader.py ./

RUN mkdir -p /app/logs

EXPOSE 8003

CMD ["python", "pipeline.py"]
FROM python:3.11

# --- BUILD ARGS ---
ARG STT_VARIANT="medium"
ARG LLM_VARIANT="3b-it-Q4_K_M"

# --- SYSTEM CONFIG ---
ENV APP_HOST=0.0.0.0
ENV APP_PORT=8003
ENV APP_LOG_LEVEL=INFO
ENV STT_MODEL_PATH=/app/models/whisper-medium
ENV STT_DEVICE=auto
ENV STT_COMPUTE_TYPE=int8
ENV STT_BEAM_SIZE=5
ENV STT_VAD_FILTER=true
ENV STT_VAD_THRESHOLD=0.5
ENV STT_VAD_MIN_SPEECH_MS=250
ENV STT_VAD_MIN_SILENCE_MS=200

ENV TTS_EN_MODEL_PATH=/app/models/TTS-CORI-EN/en_GB-cori-high.onnx
ENV TTS_EN_CONFIG_PATH=/app/models/TTS-CORI-EN/en_GB-cori-high.onnx.json
ENV TTS_AR_MODEL_PATH=/app/models/TTS-KAREEM-ARABIC/ar_JO-kareem-medium.onnx
ENV TTS_AR_CONFIG_PATH=/app/models/TTS-KAREEM-ARABIC/ar_JO-kareem-medium.onnx.json
ENV TTS_VOLUME=0.5
ENV TTS_LENGTH_SCALE=1.0
ENV TTS_NOISE_SCALE=1.0
ENV TTS_NOISE_W_SCALE=1.0
ENV TTS_NORMALIZE_AUDIO=false
ENV TTS_NCHANNELS=1
ENV TTS_SAMPWIDTH=2
ENV TTS_FRAMERATE=24000

ENV LLM_API_URL=http://host.docker.internal:2312/v1
ENV LLM_API_KEY=sk-no-key-required
ENV LLM_MODEL=local-model
ENV MCP_SERVER_URLS=http://host.docker.internal:2527/sse,http://host.docker.internal:2528/sse
ENV MCP_MAX_RETRIES=2

ENV MODELS_STORAGE_PATH=/app/models
ENV MODELS_DOWNLOAD_ON_STARTUP=false

WORKDIR /app

# Copy source code
COPY pipeline.py pipeline-streaming.py config.py downloader.py requirements.txt ./
COPY config.yaml ./

# Copy TTS models
COPY models/whisper-medium /app/models/whisper-medium
COPY models/TTS-CORI-EN /app/models/TTS-CORI-EN
COPY models/TTS-KAREEM-ARABIC /app/models/TTS-KAREEM-ARABIC

# Copy Hakeem OWW model (wake word detection)
COPY models/Hakeem/Hakeem.onnx /app/models/Hakeem.onnx
COPY models/Hakeem/Hakeem.tflite /app/models/Hakeem.tflite

RUN mkdir -p /app/MCP-servers /app/logs

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8003

CMD ["python", "pipeline.py"]
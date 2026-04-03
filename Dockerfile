FROM python:3.11


# 1. STT Model (e.g., Whisper, Thunder)
ARG STT_VARIANT="medium"
ENV STT_URL="https://huggingface.co/Systran/faster-whisper-${STT_VARIANT}/resolve/main/model.bin,\
https://huggingface.co/Systran/faster-whisper-${STT_VARIANT}/resolve/main/config.json,\
https://huggingface.co/Systran/faster-whisper-${STT_VARIANT}/resolve/main/vocabulary.txt,\
https://huggingface.co/Systran/faster-whisper-${STT_VARIANT}/resolve/main/tokenizer.json"
ENV STT_PATH="models/stt"

# 2. TTS English (e.g., Cori, Piper-v2)
ARG TTS_EN_NAME="en_GB-cori-high"
ENV TTS_EN_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/cori/high/en_GB-cori-high.onnx,\
https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/cori/high/en_GB-cori-high.onnx.json"
ENV TTS_EN_PATH="models/tts-en"

# 3. TTS Arabic (e.g., Kareem, Custom-AR)
ARG TTS_AR_NAME="ar_JO-kareem-medium"
ENV TTS_AR_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx,\
https://huggingface.co/rhasspy/piper-voices/resolve/main/ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx.json"
ENV TTS_AR_PATH="models/tts-ar"

# 4. LLM (e.g., MedGemma, BioGPT)
ARG LLM_VARIANT="3b-it-Q4_K_M"
ENV LLM_URL="https://huggingface.co/2kfi/medgemma-4B-it-fine-tuned-gguf/resolve/main/MedGemma-${LLM_VARIANT}.gguf,\
https://huggingface.co/2kfi/medgemma-4B-it-fine-tuned-gguf/resolve/main/MedGemma-mmproj.gguf"
ENV LLM_PATH="models/llm"

# --- SYSTEM CONFIG ---
ENV LLAMA_API_URL="http://10.200.71.180:2312/v1"
ENV LLAMA_API_KEY="sk-no-key-required"
ENV MCP_SERVER_URLS="http://10.200.71.180:2527/sse,http://10.200.71.180:2528/sse"
ENV STT_DEVICE="cpu"
ENV TTS_VOLUME=0.5
ENV TTS_LENGTH_SCALE=1.0
ENV TTS_NOISE_SCALE=1.0
ENV TTS_NOISE_W_SCALE=1.0
ENV TTS_NORMALIZE_AUDIO=False
ENV TTS_NCHANNELS=1
ENV TTS_SAMPWIDTH=2
ENV TTS_FRAMERATE=24000


WORKDIR /app

COPY Docker-files /app 

RUN mkdir -p /app/models

RUN mkdir -p /app/MCP-servers

RUN mkdir -p /app/logs

RUN python -c "import openwakeword; openwakeword.utils.download_models(); print('Check complete.')"

RUN pip install -r /app/requirements.txt 

RUN 

EXPOSE 8080
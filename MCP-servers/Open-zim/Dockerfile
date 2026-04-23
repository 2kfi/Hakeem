FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY src/ ./src/

RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 5000

ENV PYTHONUNBUFFERED=1
ENV ZIM_DATA_PATH=/data/zimfiles
ENV SERVER_PORT=5000
ENV SERVER_HOST=0.0.0.0

CMD ["python", "-m", "zim_mcp.server"]
# 1. Start with NVIDIA's CUDA runtime (Better for T4 compatibility)
FROM nvcr.io/nvidia/cuda:12.5.0-runtime-ubuntu22.04

# 2. Set Environment Variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# 3. Install Python 3.11 using apt
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-distutils \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 4. Set Python 3.11 as default and install Pip
RUN ln -s /usr/bin/python3.11 /usr/bin/python
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python

# 5. Setup App Directory
WORKDIR /app

# 6. Install Python Dependencies (Caching layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 7. Copy Code
COPY . .

# 8. Run your optimized pipeline
CMD ["python", "PIPELINE_optimized.py"]
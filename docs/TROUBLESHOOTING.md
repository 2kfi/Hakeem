# Troubleshooting

## Common Issues

### Models Not Found

**Symptom:** `FileNotFoundError` for model files

**Solutions:**
```bash
# Check model paths
ls -la models/

# Enable auto-download
# In config.yaml:
models:
  download_on_startup: true

# Or manually download
python downloader.py
```

---

### GPU Not Detected

**Symptom:** Using CPU instead of GPU

**Solutions:**
```bash
# NVIDIA GPU
nvidia-smi

# In config.yaml:
stt:
  device: "cuda"

# AMD ROCm
stt:
  device: "rocm"
```

---

### MCP Connection Failed

**Symptom:** MCP server errors

**Solutions:**
```bash
# Check MCP server is running
curl http://localhost:2527/sse

# In Docker, use host.docker.internal
mcp:
  servers:
    - "http://host.docker.internal:2527/sse"
```

---

### Health Check Fails

**Symptom:** `/health` returns unhealthy

**Solutions:**
```bash
# Check logs
docker-compose logs pipeline

# Or run locally
python pipeline.py

# Test manually
curl http://localhost:8003/health
```

---

### Port Already in Use

**Symptom:** `Address already in use`

**Solutions:**
```bash
# Find what's using the port
lsof -i :8003

# Change port in config.yaml
app:
  port: 8004
```

---

### TTS Voice Not Loading

**Symptom:** TTS language not working

**Solutions:**
```yaml
# Check local_path exists
tts:
  en:
    local_path: "/app/models/EN"

# Or verify HF repo
tts:
  en:
    repo: "rhasspy/piper-voices"
    voice: "en_GB/cori/high"
```

---

### Out of Memory

**Symptom:** OOM errors

**Solutions:**
```yaml
# Use lighter models
stt:
  compute_type: "int8"  # instead of float16

# Or smaller model
stt:
  model: "Systran/faster-whisper-small"
```

---

## Logs

### Enable Debug Logging

```yaml
app:
  log_level: "DEBUG"
```

### View Logs

```bash
# Docker
docker-compose logs -f pipeline

# Local
python pipeline.py
```

---

## Getting Help

1. Check logs first
2. Verify config.yaml syntax
3. Test with lighter models
4. Check [Configuration](CONFIG.md) reference
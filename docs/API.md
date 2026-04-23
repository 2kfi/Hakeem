# API Reference

## Endpoints

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "device": "cpu",
  "models_loaded": {
    "stt": true,
    "tts_en": true,
    "tts_ar": true
  }
}
```

---

### POST /process-audio

Process audio file, return audio response (non-streaming).

**Request:**
- Content-Type: `multipart/form-data`
- Body: `file` - Audio file (wav, mp3, etc.)

**Response:**
- Content-Type: `audio/wav`
- Body: Audio file

**Example:**
```bash
curl -X POST http://localhost:8003/process-audio \
  -F "file=@audio.wav" \
  --output response.wav
```

---

### POST /process-audio-stream

Process audio file, return streaming audio response.

**Request:**
- Content-Type: `multipart/form-data`
- Body: `file` - Audio file

**Response:**
- Content-Type: `audio/wav`
- Body: Streaming audio

**Example:**
```bash
curl -X POST http://localhost:8003/process-audio-stream \
  -F "file=@audio.wav" \
  --output stream_response.wav
```

---

## Response Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad request (missing file) |
| 422 | Validation error |
| 500 | Internal server error |
| 503 | Service unavailable |

## Error Response

```json
{
  "detail": "Error message"
}
```
# Changelog - LLMSIMT-Hakeem

## ALPHA V.17 - Wake Word Client

### Added
- **wake_word_client.py**: New client script that:
  - Listens for wake word "Hakeem" using OWW model
  - Records speech until silence detection (webrtcvad)
  - Sends audio to pipeline API
  - Plays TTS response via pyaudio
  - Command line arguments for API URL, model path, threshold, etc.
  - Debug mode to save recorded audio
- Added webrtcvad to requirements.txt for silence detection

### Changed
- **Single Repository Structure**: Removed Docker-files subfolder
- **OWW Model**: Now uses local Hakeem model instead of downloading
- **Dockerfile**: Updated to copy local models instead of downloading
- **Config**: Unified config.yaml at root level
- **docker-compose.yml**: Added at root for deployment

### Fixed
- TTS now uses LLM response language (via langdetect) instead of STT language
- LLM model now configurable
- VAD parameters now tunable
- Model download disabled by default
- Proper error handling instead of silent failures

---

## Previous Versions

### ALPHA V.16 (Bug Fixes)
- Fixed MCP tools schema caching
- Added LLM API timeout (60s)
- Fixed file handle leaks
- Fixed endpoint typo (prosess → process)

### ALPHA V.15
- Added input validation
- Fixed STT failure handling

### ALPHA V.14
- Initial pipeline fixes
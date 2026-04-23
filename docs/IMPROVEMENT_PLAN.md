# Improvement Plan

Based on 60 identified improvements, here is the prioritized plan.

## Quick Wins (1-2 hrs each)

### 1. Extract Shared Code
**Issue:** #1-8 (duplication)

| Task | Action |
|------|--------|
| 1.1 | Create `src/mcp.py` with shared `MCPSessionManager`, `MCPWrapper` |
| 1.2 | Create `src/shared.py` with `_detect_language()`, `_validate_audio_format()` |
| 1.3 | Create `src/config.py` - move config loading from root to package |

**Files to create:**
- `src/__init__.py`
- `src/mcp.py`
- `src/shared.py`

### 2. Add Tests
**Issue:** #31-35

| Task | Action |
|------|--------|
| 2.1 | Create `tests/test_config.py` |
| 2.2 | Create `tests/test_shared.py` |
| 2.3 | Add GitHub Actions workflow `.github/workflows/test.yml` |

**Files to create:**
- `tests/__init__.py`
- `tests/test_config.py`
- `tests/test_shared.py`
- `.github/workflows/test.yml`

### 3. Dockerfile Healthcheck
**Issue:** #53

| Task | Action |
|------|--------|
| 3.1 | Add HEALTHCHECK to Dockerfile |

### 4. Config Validation
**Issue:** #15-18

| Task | Action |
|------|--------|
| 4.1 | Add pydantic model for Config validation |
| 4.2 | Add config schema file |

---

## Medium Effort (4-8 hrs each)

### 5. Split Pipeline
**Issue:** #25

| Task | Action |
|------|--------|
| 5.1 | Create `src/stt.py` - STT abstraction |
| 5.2 | Create `src/tts.py` - TTS abstraction |
| 5.3 | Create `src/llm.py` - LLM wrapper |
| 5.4 | Refactor `pipeline.py` to use modules |
| 5.5 | Refactor `pipeline-streaming.py` to use modules |

### 6. Error Handling Improvements
**Issue:** #9-14

| Task | Action |
|------|--------|
| 6.1 | Add retry logic for STT failures |
| 6.2 | Add retry logic for TTS failures |
| 6.3 | Add validation for LLM API key |
| 6.4 | Handle empty tool results gracefully |

### 7. Better Logging
**Issue:** #40

| Task | Action |
|------|--------|
| 7.1 | Replace print() with structured logging |
| 7.2 | Add request correlation IDs |
| 7.3 | Add log levels by component |

---

## Major Refactors (1-2 days each)

### 8. Plugin System for Languages
**Issue:** #27, #51

| Task | Action |
|------|--------|
| 8.1 | Make TTS languages pluggable |
| 8.2 | Add config-driven language loading |
| 8.3 | Allow dynamic language addition |

### 9. Docker Optimizations
**Issue:** #54-55

| Task | Action |
|------|--------|
| 9.1 | Add multi-stage build |
| 9.2 | Create .dockerignore |
| 9.3 | Pin versions in requirements.txt |

### 10. API Improvements
**Issue:** #44-47

| Task | Action |
|------|--------|
| 10.1 | Add API versioning |
| 10.2 | Add OpenAPI docs endpoint |
| 10.3 | Add request/response schemas with pydantic |

---

## Not Recommended (Low Value)

| # | Issue | Why |
|-----|------|-----|
| #22 | Async file I/O - already using to_thread |
| #23 | Connection pooling - aiohttp vs requests |
| #28 | Global variables - refactoring too risky |
| #36 | Input sanitization - FastAPI handles this |

---

## Recommended Order

```
Phase 1: Quick Wins (Week 1)
├── 1. Extract shared MCP code
├── 2. Add tests skeleton
├── 3. Dockerfile healthcheck

Phase 2: Clean Up (Week 2)
├── 5. Split pipeline into modules
├── 6. Error handling improvements

Phase 3: Polish (Week 3)
├── 7. Better logging
├── 10. API improvements

Phase 4: Future
├── 8. Plugin system
├── 9. Docker optimizations
```

---

## Implementation Notes

### Shared Code Structure
```
src/
├── __init__.py
├── config.py      # from root config.py
├── mcp.py        # extracted from pipeline.py
├── shared.py      # shared utilities
├── stt.py        # whisper wrapper
├── tts.py        # piper wrapper
├── llm.py        # llm wrapper
└── api.py        # FastAPI app
```

### Config Validation
Use pydantic:
```python
from pydantic import BaseModel, Field

class TTSLanguage(BaseModel):
    repo: str | None = None
    voice: str | None = None
    local_path: str | None = None
```

### Test Structure
```
tests/
├── __init__.py
├── test_config.py
├── test_shared.py
├── fixtures/
│   ├── audio/
│   │   └── test.wav
│   └── config/
│       └── valid.yaml
```

---

## Success Metrics

- [ ] Reduce pipeline.py from 510 lines to ~150 lines
- [ ] Remove code duplication between pipelines
- [ ] Add unit test coverage > 50%
- [ ] Add Dockerfile healthcheck
- [ ] Add CI pipeline
- [ ] Config validation with clear errors
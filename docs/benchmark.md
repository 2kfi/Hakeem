<!-- Arkan Fakoseh -  @2kfi on github -->
# Benchmark Testing

Run medical USMLE-style questions against the app's configured LLM (from `config.yaml`).

## Usage

```bash
# Terminal 1: start app with desired model + RAG config
python3 app.py --no-auth

# Terminal 2: run benchmark
python3 tests/benchmark/benchmark_rag.py \
    --app-url http://localhost:8000 \
    --delay 10
```

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `--app-url` | `http://localhost:8000` | Hakeem app URL |
| `--questions` | `medqa_three_pillars_100.txt` | Path to questions file |
| `--delay` | `0.5` | Seconds to wait between questions |
| `--system-prompt` | *(strict letter-only)* | Override system prompt for benchmark |
| `--tools` | *(disabled)* | Enable tool calling (calculator, weather, etc.) |

By default, tools are disabled and a strict letter-answer prompt is used. Pass `--tools` if you want to test tool calling. All other LLM and RAG settings come from `config.yaml`.

## Checkpoint Resume

If interrupted, re-run with the same args — it picks up where it left off.

```bash
# Interrupted at question 42
python3 tests/benchmark/benchmark_rag.py --delay 10
# → "Checkpoint: 41 questions done, resuming from line 42"
```

## Output

Single JSON at `tests/benchmark/output/{model}_output.json` (model auto-detected from app):

```json
[
  {
    "question": "A 23-year-old pregnant woman...",
    "options": "A: Ampicillin, B: Ceftriaxone, C: Doxycycline, D: Nitrofurantoin",
    "llm_answer": "D",
    "correct_answer": "D",
    "correct": true,
    "llm_response_full": "The correct answer is D (Nitrofurantoin)...",
    "elapsed": 2.3
  }
]
```

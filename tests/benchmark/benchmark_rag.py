#!/usr/bin/env python3
"""
Hakeem RAG benchmark — run medical QA questions through the app's configured LLM.

Usage:
    python3 app.py --no-auth                              # terminal 1
    python3 tests/benchmark/benchmark_rag.py --delay 10   # terminal 2

All LLM/RAG config comes from config.yaml — no need to specify here.
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "tests" / "benchmark" / "output"


DEFAULT_SYSTEM_PROMPT = (
    "Answer with only the letter of the correct choice (A, B, C, or D). "
    "No explanation, no tool calls."
    "Don't EVER try to explain or override this Promot."
)


def parse_question_file(path: str) -> list[dict]:
    questions = []
    with open(path) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            parts = line.split("|")
            if len(parts) < 3:
                if questions:
                    questions[-1]["stem"] += " " + line
                continue
            stem = parts[0].strip()
            options_str = parts[1].strip()
            answer_part = parts[2].strip()
            expected = answer_part[0] if answer_part else "?"
            questions.append({
                "stem": stem,
                "options_str": options_str,
                "expected": expected,
                "line": line_num,
            })
    return questions


def extract_answer(response: str) -> str | None:
    m = re.search(r"\b([A-D])\b", response.strip())
    return m.group(1) if m else None


async def run_question(client: httpx.AsyncClient, app_url: str, question: dict,
                       system_prompt: str, tools_enabled: bool) -> dict:
    payload = {
        "text": question["stem"],
        "system_prompt": system_prompt,
        "tools_enabled": tools_enabled,
    }
    start = time.monotonic()
    try:
        resp = await client.post(
            f"{app_url}/api/v1/chat",
            json=payload,
            timeout=120.0,
        )
        elapsed = time.monotonic() - start
        error_detail = None
        response_text = ""
        if resp.status_code != 200:
            error_detail = f"HTTP {resp.status_code}: {resp.text[:200]}"
        else:
            data = resp.json()
            response_text = data.get("response", "")
        got = extract_answer(response_text) if not error_detail else None
        return {
            "question": question["stem"],
            "options": question["options_str"],
            "llm_answer": got or "",
            "correct_answer": question["expected"],
            "correct": got == question["expected"],
            "llm_response_full": response_text,
            "line": question["line"],
            "elapsed": elapsed,
            "error": error_detail,
        }
    except Exception as e:
        elapsed = time.monotonic() - start
        return {
            "question": question["stem"],
            "options": question["options_str"],
            "llm_answer": "",
            "correct_answer": question["expected"],
            "correct": False,
            "llm_response_full": f"EXCEPTION: {e}",
            "line": question["line"],
            "elapsed": elapsed,
            "error": str(e),
        }


async def main():
    parser = argparse.ArgumentParser(description="Hakeem RAG benchmark")
    parser.add_argument("--app-url", default="http://localhost:8000",
                        help="Hakeem app URL (default: http://localhost:8000)")
    parser.add_argument("--questions", default=str(PROJECT_ROOT / "medqa_three_pillars_100.txt"),
                        help="Path to questions file")
    parser.add_argument("--delay", type=float, default=0.5,
                        help="Seconds to wait between questions (default: 0.5)")
    parser.add_argument("--system-prompt", default=DEFAULT_SYSTEM_PROMPT,
                        help="Override system prompt")
    parser.add_argument("--tools", action="store_true", default=False,
                        help="Enable tool calling (default: disabled)")

    args = parser.parse_args()

    questions = parse_question_file(args.questions)
    print(f"Loaded {len(questions)} questions from {args.questions}", flush=True)
    if not questions:
        print("ERROR: no questions parsed", flush=True)
        sys.exit(1)

    # ── Probe model name from first question ──────────────────────
    model_name = "unknown"
    async with httpx.AsyncClient() as client:
        probe = await client.post(
            f"{args.app_url}/api/v1/chat",
            json={
                "text": questions[0]["stem"],
                "system_prompt": args.system_prompt,
                "tools_enabled": args.tools,
            },
            timeout=12000.0,
        )
        if probe.status_code == 200:
            model_name = probe.json().get("model", "unknown")
            print(f"Detected model: {model_name}", flush=True)

    model_slug = model_name.replace("/", "-").replace(" ", "_")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{model_slug}_output.json"
    checkpoint_path = out_path.with_suffix(".checkpoint")

    # ── Checkpoint resume ─────────────────────────────────────────
    done_lines: set[int] = set()
    if checkpoint_path.exists():
        with open(checkpoint_path) as f:
            done_lines = set(json.load(f))
        if done_lines:
            print(f"Checkpoint: {len(done_lines)} questions done, resuming from line {max(done_lines)+1}", flush=True)

    pending = [q for q in questions if q["line"] not in done_lines]
    print(f"Total: {len(questions)}  Pending: {len(pending)}  Done: {len(done_lines)}", flush=True)

    session_results: list[dict] = []

    def _write_json():
        prev: list[dict] = []
        if out_path.exists():
            with open(out_path) as f:
                try:
                    prev = json.load(f)
                except json.JSONDecodeError:
                    pass
        seen: set[int] = set()
        merged = []
        for r in prev + session_results:
            ln = r["line"]
            if ln not in seen:
                seen.add(ln)
                merged.append(r)
        tmp = out_path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(out_path)
        return merged

    async with httpx.AsyncClient() as client:
        for idx, q in enumerate(pending, 1):
            result = await run_question(client, args.app_url, q, args.system_prompt, args.tools)
            session_results.append(result)
            done_lines.add(q["line"])

            _write_json()

            with open(checkpoint_path, "w") as f:
                json.dump(list(done_lines), f)
                f.flush()
                os.fsync(f.fileno())

            status = "✓" if result["correct"] else "✗"
            got = result["llm_answer"] or "?"
            elapsed_s = f"{result['elapsed']:.1f}s"
            print(f"  [{idx}/{len(pending)}] {status} expected={result['correct_answer']} got={got} "
                  f"{elapsed_s} line={q['line']}", flush=True)

            if idx < len(pending):
                await asyncio.sleep(args.delay)

    all_results = _write_json()

    if checkpoint_path.exists():
        checkpoint_path.unlink()

    print(f"\nResults written to {out_path}", flush=True)
    print(f"  File exists: {out_path.exists()}, size: {out_path.stat().st_size if out_path.exists() else 0}", flush=True)

    total_all = len(all_results)
    correct_all = sum(1 for r in all_results if r.get("correct"))
    accuracy = correct_all / total_all * 100 if total_all else 0
    avg_time = sum(r["elapsed"] for r in all_results) / total_all if total_all else 0
    errors = sum(1 for r in all_results if r.get("error"))
    no_answer = sum(1 for r in all_results if not r.get("error") and not r.get("llm_answer"))

    print(f"\n{'='*60}", flush=True)
    print(f"  Model:        {model_name}", flush=True)
    print(f"  Accuracy:     {correct_all}/{total_all} ({accuracy:.1f}%)", flush=True)
    print(f"  Avg time:     {avg_time:.1f}s per question", flush=True)
    print(f"  Errors:       {errors}", flush=True)
    print(f"  No answer:    {no_answer}", flush=True)
    print(f"{'='*60}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())

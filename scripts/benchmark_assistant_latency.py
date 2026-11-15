"""Benchmark deterministic assistant paths (no live Gemini).

Prefer pytest for timed runs:
  pytest tests/unit/test_assistant_orchestrator.py -q
Logs with percentiles: grep assistant_request_metrics in uvicorn output.
"""

from __future__ import annotations


def main() -> None:
    print("See docs/gemini-performance.md for benchmark procedure.")


if __name__ == "__main__":
    main()

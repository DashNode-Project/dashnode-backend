"""Smoke test: POST /api/v1/ai/text-generate against a running API (EP-10).

Usage (after login cookie or run against dev with session):
  python scripts/smoke_ep10_text_chat.py --base-url http://127.0.0.1:8000 --cookie "<dashnode_session>"
"""

from __future__ import annotations

import argparse
import json
import sys

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test Gemini text path for EP-10")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--cookie", required=True, help="Session cookie value (dashnode_session)")
    parser.add_argument("--text", default="Resume en una frase qué es DashNode.")
    parser.add_argument("--project-id", default=None)
    args = parser.parse_args()

    cookies = {"dashnode_session": args.cookie}
    body: dict[str, str] = {"text": args.text}
    if args.project_id:
        body["project_id"] = args.project_id

    with httpx.Client(timeout=90.0) as client:
        response = client.post(
            f"{args.base_url.rstrip('/')}/api/v1/ai/text-generate",
            json=body,
            cookies=cookies,
        )
    print(json.dumps(response.json(), ensure_ascii=False, indent=2))
    return 0 if response.status_code == 200 else 1


if __name__ == "__main__":
    sys.exit(main())

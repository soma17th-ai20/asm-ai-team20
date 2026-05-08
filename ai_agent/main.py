from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from ai_agent.service import run_agentic_flow
else:
    from .service import run_agentic_flow


def main() -> None:
    parser = argparse.ArgumentParser(description="Agentic flow demo")
    parser.add_argument("prompt", help="사용자 자연어 요청")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="외부 LLM 호출 없이 fallback 파서만 사용",
    )
    args = parser.parse_args()

    result = run_agentic_flow(args.prompt, use_llm=not args.no_llm)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

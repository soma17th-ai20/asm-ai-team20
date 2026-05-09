"""간단한 CLI — 스케줄러/수동 실행용.

  python -m backend.cli init        # 스키마만 생성
  python -m backend.cli crawl       # 크롤만 실행 (임베딩 X)
  python -m backend.cli embed       # 미임베딩 공지 임베딩
  python -m backend.cli ingest      # crawl + embed 풀 파이프라인
"""
from __future__ import annotations

import argparse
import logging
import sys


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(prog="backend.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="DB 스키마 생성")
    p_crawl = sub.add_parser("crawl", help="크롤만 실행")
    p_crawl.add_argument("--source", default=None, help="단일 source_id (생략 시 전체)")
    sub.add_parser("embed", help="미임베딩 공지 임베딩")
    p_ingest = sub.add_parser("ingest", help="crawl + embed")
    p_ingest.add_argument("--source", default=None)

    args = parser.parse_args(argv)

    # config 로드는 명령 실행 시점에. (init 외에는 OPENAI_API_KEY 필요)
    if args.cmd == "init":
        from db.connection import init_schema

        init_schema()
        print("schema initialized")
        return 0

    if args.cmd == "crawl":
        from db.connection import init_schema
        from service.ingestion import build_crawl_service

        init_schema()
        reports = build_crawl_service().crawl_all(args.source)
        for r in reports:
            print(
                f"{r.source_id}: fetched={r.fetched} inserted={r.inserted} "
                f"dup={r.duplicates} errors={len(r.errors)}"
            )
        return 0

    if args.cmd == "embed":
        from db.connection import init_schema
        from service.ingestion import embed_pending

        init_schema()
        n = embed_pending()
        print(f"embedded {n} notices")
        return 0

    if args.cmd == "ingest":
        from service.ingestion import run_full_ingestion

        report = run_full_ingestion(args.source)
        for r in report.crawl_reports:
            print(
                f"{r.source_id}: fetched={r.fetched} inserted={r.inserted} "
                f"dup={r.duplicates} errors={len(r.errors)}"
            )
        print(f"embedded={report.embedded} model={report.embedding_model}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

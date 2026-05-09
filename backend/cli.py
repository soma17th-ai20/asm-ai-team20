"""간단한 CLI — 스케줄러/수동 실행용.

  python -m cli init                         # 스키마만 생성
  python -m cli crawl                        # 크롤만 실행 (임베딩 X)
  python -m cli embed                        # 미임베딩 공지 임베딩
  python -m cli ingest                       # crawl + embed 풀 파이프라인
  python -m cli rematch [--threshold 0.40]   # 기존 notices 전체를 재매칭 → 큐 적재
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
    p_rematch = sub.add_parser(
        "rematch",
        help="기존 notices 전체를 user_interests에 대해 재매칭 → notifications/Redis 큐 적재",
    )
    p_rematch.add_argument(
        "--threshold", type=float, default=None,
        help="cosine 임계값 일시 오버라이드 (기본은 settings.similarity_threshold)",
    )
    p_rematch.add_argument(
        "--limit", type=int, default=None,
        help="최근 N개만 재매칭 (생략 시 전체)",
    )

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

    if args.cmd == "rematch":
        from sqlalchemy import text

        from config import settings
        from db.connection import init_schema, session_scope
        from service.filter import push_notice_to_redis_queue

        if args.threshold is not None:
            settings.similarity_threshold = args.threshold  # type: ignore[attr-defined]
        init_schema()

        sql = "SELECT id FROM notices ORDER BY id DESC"
        params: dict = {}
        if args.limit is not None:
            sql += " LIMIT :lim"
            params["lim"] = args.limit
        with session_scope() as s:
            nids = [r.id for r in s.execute(text(sql), params).fetchall()]

        print(f"rematch: threshold={settings.similarity_threshold} notices={len(nids)}")
        for i, nid in enumerate(nids, 1):
            try:
                with session_scope() as s:
                    push_notice_to_redis_queue(s, nid)
            except Exception as e:  # noqa: BLE001
                print(f"  notice {nid} error: {e}")
            if i % 20 == 0:
                print(f"  {i}/{len(nids)}")
        print("done")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

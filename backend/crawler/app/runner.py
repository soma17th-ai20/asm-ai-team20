from __future__ import annotations

import argparse
import logging
import time
from typing import Optional

from . import scrapers, storage
from .config import CrawlerConfig, SiteConfig, load_config
from .fetcher import http_client
from .models import CrawlReport, RawNotice
from .scrapers.base import ScrapeContext

log = logging.getLogger("crawler")


def crawl_site(config: CrawlerConfig, site: SiteConfig) -> CrawlReport:
    started = CrawlReport.now_iso()
    errors: list[str] = []
    items: list[RawNotice] = []

    try:
        with http_client(config.defaults) as client:
            ctx = ScrapeContext(site=site, defaults=config.defaults, client=client)
            scraper = scrapers.get(site.scraper)
            items = list(scraper(ctx))
    except Exception as exc:  # noqa: BLE001 — 외부 사이트 장애로 다음 사이트로 넘어간다
        errors.append(f"fetch/parse failed: {exc!r}")

    inserted = duplicates = 0
    if items:
        with storage.connect() as conn:
            inserted, duplicates = storage.insert_many(conn, items)

    return CrawlReport(
        source_id=site.id,
        fetched=len(items),
        inserted=inserted,
        duplicates=duplicates,
        errors=errors,
        started_at=started,
        finished_at=CrawlReport.now_iso(),
    )


def crawl_all(config: CrawlerConfig, source_id: Optional[str] = None) -> list[CrawlReport]:
    reports: list[CrawlReport] = []
    targets = [config.site(source_id)] if source_id else list(config.enabled_sites())
    for i, site in enumerate(targets):
        if i > 0:
            time.sleep(config.defaults.request_delay_seconds)
        log.info("crawl start: %s", site.id)
        report = crawl_site(config, site)
        log.info(
            "crawl done: %s — fetched=%d inserted=%d dup=%d errors=%d",
            site.id, report.fetched, report.inserted, report.duplicates, len(report.errors),
        )
        reports.append(report)
    return reports


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Notice crawler runner")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_crawl = sub.add_parser("crawl", help="실제 크롤링 + DB 저장")
    p_crawl.add_argument("--source", help="특정 site id만 크롤")

    p_dry = sub.add_parser("dry-run", help="가져오지만 DB에 저장하지 않고 결과만 출력")
    p_dry.add_argument("--source", required=True)
    p_dry.add_argument("--limit", type=int, default=10)

    sub.add_parser("list-sites", help="등록된 사이트 목록")

    args = parser.parse_args()
    config = load_config()

    if args.cmd == "list-sites":
        for s in config.sites:
            print(f"  - {s.id:20s} enabled={s.enabled} render={s.render} url={s.url}")
        return

    if args.cmd == "dry-run":
        site = config.site(args.source)
        with http_client(config.defaults) as client:
            ctx = ScrapeContext(site=site, defaults=config.defaults, client=client)
            items = list(scrapers.get(site.scraper)(ctx))
        for n in items[: args.limit]:
            print(f"- {n.title} | {n.url} | {n.posted_at or ''}")
        print(f"total parsed: {len(items)}")
        return

    if args.cmd == "crawl":
        reports = crawl_all(config, args.source)
        for r in reports:
            print(r.model_dump_json(indent=2))


if __name__ == "__main__":
    main()

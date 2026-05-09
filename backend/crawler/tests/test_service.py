from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# 프로젝트 루트를 path에 추가
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import CrawlerConfig, Defaults, SiteConfig  # noqa: E402
from app.models import RawNotice  # noqa: E402
from app.service import NoticeCrawlService  # noqa: E402
from app.storage import SQLiteNoticeRepository  # noqa: E402


def test_service_uses_repository_interface():
    site = SiteConfig(
        id="test_source",
        name="테스트",
        url="https://example.com",
        scraper="fake",
        category="notice",
        enabled=True,
        render="http",
    )
    config = CrawlerConfig(
        sites=(site,),
        defaults=Defaults(
            user_agent="Mozilla/5.0",
            request_delay_seconds=0,
            request_timeout_seconds=5,
            max_items_per_run=10,
        ),
    )

    def fake_scraper(_: object) -> list[RawNotice]:
        return [
            RawNotice(
                source_id="test_source",
                title="통합 인터페이스 테스트",
                url="https://example.com/notices/1",
                body="본문",
            ),
        ]

    with tempfile.TemporaryDirectory() as tmp:
        repo = SQLiteNoticeRepository(Path(tmp) / "test.db")
        service = NoticeCrawlService(
            config=config,
            repository=repo,
            scraper_resolver=lambda name: fake_scraper if name == "fake" else None,
        )

        report = service.crawl_site("test_source")

        assert report.fetched == 1
        assert report.inserted == 1
        assert service.count_notices("test_source") == 1
        assert service.list_notices("test_source", limit=1)[0].body == "본문"


if __name__ == "__main__":
    test_service_uses_repository_interface()
    print("all tests passed")

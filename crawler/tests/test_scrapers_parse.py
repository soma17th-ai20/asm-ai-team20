from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import scrapers  # noqa: E402
from app.config import Defaults, SiteConfig  # noqa: E402
from app.scrapers.base import ScrapeContext  # noqa: E402

DEFAULTS = Defaults(
    user_agent="ua",
    request_delay_seconds=0,
    request_timeout_seconds=5,
    max_items_per_run=50,
)


def _ctx(site_id: str, scraper: str, url: str, html: str) -> ScrapeContext:
    site = SiteConfig(
        id=site_id, name=site_id, url=url, scraper=scraper,
        category="test", enabled=True, render="http",
    )
    return ScrapeContext(site=site, defaults=DEFAULTS, html=html)


def test_snu_cse_table_layout():
    html = """
    <html><body><table><tbody>
      <tr><td>1</td><td><a href="/community/notice/1">[안내] 장학금 공지</a></td><td></td><td>2026-01-02</td></tr>
      <tr><td>2</td><td><a href="/community/notice/2">[모집] 인턴십 모집</a></td><td></td><td>2026-01-03</td></tr>
    </tbody></table></body></html>
    """
    ctx = _ctx("snu_cse_notice", "snu_cse_notice", "https://cse.snu.ac.kr/community/notice", html)
    items = list(scrapers.get("snu_cse_notice")(ctx))
    titles = [i.title for i in items]
    assert "[안내] 장학금 공지" in titles
    assert "[모집] 인턴십 모집" in titles
    assert all(str(i.url).startswith("https://cse.snu.ac.kr/") for i in items)


def test_saramin_with_company():
    html = """
    <html><body>
      <div class="list_item">
        <a class="job_tit" href="/zf_user/jobs/relay/view?rec_idx=123"><span>AI 엔지니어 채용</span></a>
        <div class="company_nm">테스트컴퍼니</div>
      </div>
    </body></html>
    """
    ctx = _ctx("saramin_hot100", "saramin_hot100",
               "https://www.saramin.co.kr/zf_user/jobs/hot100", html)
    items = list(scrapers.get("saramin_hot100")(ctx))
    assert items, "should parse at least one item"
    assert "[테스트컴퍼니]" in items[0].title


def test_jobkorea_basic():
    html = """
    <html><body><ul class="lists">
      <li><a href="/Recruit/GI_Read/12345"><span class="title">백엔드 개발자</span></a>
          <span class="name">샘플코퍼레이션</span></li>
    </ul></body></html>
    """
    ctx = _ctx("jobkorea_ai", "jobkorea_ai",
               "https://www.jobkorea.co.kr/recruit/ai-jobs", html)
    items = list(scrapers.get("jobkorea_ai")(ctx))
    assert items
    assert "백엔드 개발자" in items[0].title


def test_naver_card_layout():
    html = """
    <html><body>
      <a class="card_link" href="/rcrt/view.do?annoId=99">
        <strong class="card_title">신입 백엔드 채용</strong>
        <p class="card_info">서비스개발 / 정규직</p>
      </a>
    </body></html>
    """
    ctx = _ctx("naver_recruit", "naver_recruit",
               "https://recruit.navercorp.com/rcrt/list.do", html)
    items = list(scrapers.get("naver_recruit")(ctx))
    assert items
    assert items[0].title == "신입 백엔드 채용"


if __name__ == "__main__":
    test_snu_cse_table_layout()
    test_saramin_with_company()
    test_jobkorea_basic()
    test_naver_card_layout()
    print("all parser tests passed")

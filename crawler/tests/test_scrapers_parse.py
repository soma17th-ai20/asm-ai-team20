from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import Defaults, SiteConfig  # noqa: E402
from app.scrapers import (  # noqa: E402
    jobkorea_ai,
    naver_cafe_notice,
    naver_recruit,
    saramin_hot100,
    snu_cba_notice,
    snu_cse_notice,
)

DEFAULTS = Defaults(
    user_agent="ua",
    request_delay_seconds=0,
    request_timeout_seconds=5,
    max_items_per_run=50,
)


def _site(id_: str, url: str) -> SiteConfig:
    return SiteConfig(
        id=id_, name=id_, url=url, scraper=id_,
        category="test", enabled=True, render="http",
    )


def test_snu_cse_table_layout():
    html = """
    <html><body><table><tbody>
      <tr><td>1</td><td><a href="/community/notice/1">[안내] 장학금 공지</a></td><td></td><td>2026-01-02</td></tr>
      <tr><td>2</td><td><a href="/community/notice/2">[모집] 인턴십 모집</a></td><td></td><td>2026-01-03</td></tr>
    </tbody></table></body></html>
    """
    site = _site("snu_cse_notice", "https://cse.snu.ac.kr/community/notice")
    items = snu_cse_notice.parse_html(html, site, DEFAULTS)
    titles = [i.title for i in items]
    assert "[안내] 장학금 공지" in titles
    assert "[모집] 인턴십 모집" in titles
    assert all(str(i.url).startswith("https://cse.snu.ac.kr/") for i in items)


def test_snu_cba_basic():
    html = """
    <html><body><ul class="notice-list">
      <li><a href="/newsroom/notice/10"><strong class="title">CBA 장학금 안내</strong><span class="date">2026-02-01</span></a></li>
    </ul></body></html>
    """
    site = _site("snu_cba_notice", "https://cba.snu.ac.kr/newsroom/notice")
    items = snu_cba_notice.parse_html(html, site, DEFAULTS)
    assert items
    assert items[0].title == "CBA 장학금 안내"
    assert "cba.snu.ac.kr" in str(items[0].url)


def test_saramin_with_company():
    html = """
    <html><body>
      <div class="list_item">
        <a class="job_tit" href="/zf_user/jobs/relay/view?rec_idx=123"><span>AI 엔지니어 채용</span></a>
        <div class="company_nm">테스트컴퍼니</div>
      </div>
    </body></html>
    """
    site = _site("saramin_hot100", "https://www.saramin.co.kr/zf_user/jobs/hot100")
    items = saramin_hot100.parse_html(html, site, DEFAULTS)
    assert items, "should parse at least one item"
    assert "[테스트컴퍼니]" in items[0].title


def test_jobkorea_fragment_parses_recruit_items():
    html = """
    <ul class="recruit-list">
      <li class="recruit-item">
        <div class="company"><h2 class="company-name"><a href="/Recruit/Co_Read/C/x">샘플코퍼레이션</a></h2></div>
        <a class="recruit-link" href="/Recruit/GI_Read/12345?sc=322" data-applyclosedt="2026-06-30 23:00:00">
          <div class="recruit-title"><h3 class="title">백엔드 엔지니어</h3></div>
        </a>
      </li>
    </ul>
    """
    site = _site("jobkorea_ai", "https://www.jobkorea.co.kr/recruit/ai-jobs")
    items = jobkorea_ai.parse_html_fragment(html, site, DEFAULTS)
    assert items
    assert "[샘플코퍼레이션] 백엔드 엔지니어" == items[0].title
    assert items[0].summary == "2026-06-30 23:00:00"
    assert "jobkorea.co.kr/Recruit/GI_Read/12345" in str(items[0].url)


def test_naver_payload_basic():
    payload = {
        "result": "Y",
        "list": [
            {
                "annoId": 30001234,
                "annoSubject": "AI 엔지니어 (체험형 인턴)",
                "sysCompanyCdNm": "NAVER",
                "staYmdTime": "2026.04.29 10:00:00",
                "endYmdTime": "2026.05.07 23:59:00",
                "entTypeCdNm": "신입",
                "stateCdNm": "채용진행중",
                "reqTypeCdNm": "수시",
            },
            {"annoId": None, "annoSubject": "skipped"},  # 안전: 무시되어야 함
        ],
    }
    site = _site("naver_recruit", "https://recruit.navercorp.com/rcrt/list.do")
    items = naver_recruit.parse_payload(payload, site, DEFAULTS)
    assert len(items) == 1
    assert items[0].title.startswith("[NAVER]")
    assert "annoId=30001234" in str(items[0].url)
    assert "신입" in (items[0].summary or "")


def test_naver_cafe_payload_basic():
    payload = {
        "message": {
            "result": {
                "articleList": [
                    {
                        "articleId": 2,
                        "subject": "소마 장학금 공지",
                        "writerNickname": "양현서",
                        "writeDateTimestamp": 1778256759050,
                        "readCount": 0,
                        "commentCount": 0,
                    },
                    {"articleId": None, "subject": "skip"},
                    {"articleId": 3, "subject": ""},
                ]
            }
        }
    }
    site = _site(
        "naver_cafe_notice",
        "https://cafe.naver.com/f-e/cafes/31723403/menus/2",
    )
    items = naver_cafe_notice.parse_payload(payload, site, DEFAULTS)
    assert len(items) == 1
    assert items[0].title == "소마 장학금 공지"
    assert "cafes/31723403/articles/2" in str(items[0].url)
    assert items[0].summary and "by 양현서" in items[0].summary
    # writeDateTimestamp(epoch ms) → ISO 변환 확인
    assert items[0].posted_at and items[0].posted_at.startswith("2026-")


def test_naver_cafe_url_pattern_required():
    """카페 URL 패턴이 안 맞으면 빈 결과 — 잘못된 sites.json 등록을 방어한다."""
    site = _site("naver_cafe_notice", "https://cafe.naver.com/some-other-path")
    items = naver_cafe_notice.parse_payload(
        {"message": {"result": {"articleList": [{"articleId": 1, "subject": "x"}]}}},
        site,
        DEFAULTS,
    )
    assert items == []


def test_safe_href_filters_javascript_anchor():
    """공유 버튼 같은 javascript: 링크가 통째로 결과를 죽이지 않아야 한다."""
    html = """
    <html><body><table><tbody>
      <tr><td><a href="javascript:share('blog','...');">공유하기</a></td><td>2026-01-01</td></tr>
      <tr><td><a href="/community/notice/77">정상 공지</a></td><td>2026-01-02</td></tr>
    </tbody></table></body></html>
    """
    site = _site("snu_cse_notice", "https://cse.snu.ac.kr/community/notice")
    items = snu_cse_notice.parse_html(html, site, DEFAULTS)
    titles = [i.title for i in items]
    assert "정상 공지" in titles
    assert all("공유하기" not in t for t in titles)


if __name__ == "__main__":
    test_snu_cse_table_layout()
    test_snu_cba_basic()
    test_saramin_with_company()
    test_jobkorea_fragment_parses_recruit_items()
    test_naver_payload_basic()
    test_naver_cafe_payload_basic()
    test_naver_cafe_url_pattern_required()
    test_safe_href_filters_javascript_anchor()
    print("all parser tests passed")

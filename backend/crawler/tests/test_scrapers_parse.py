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
        <a class="job_tit" href="/zf_user/jobs/relay/view?rec_idx=123"><span>AI 엔지니어 채용 스크랩</span></a>
        <div class="company_nm">테스트컴퍼니 관심기업 등록</div>
      </div>
    </body></html>
    """
    site = _site("saramin_hot100", "https://www.saramin.co.kr/zf_user/jobs/hot100")
    items = saramin_hot100.parse_html(html, site, DEFAULTS)
    assert items, "should parse at least one item"
    assert "[테스트컴퍼니]" in items[0].title
    assert "관심기업 등록" not in items[0].title
    assert "스크랩" not in items[0].title
    assert items[0].summary == "테스트컴퍼니"


def test_saramin_strips_duplicate_company_prefix_from_title():
    html = """
    <html><body>
      <div class="list_item">
        <a class="job_tit" href="/zf_user/jobs/relay/view?rec_idx=123"><span>[인컴이즈] 광고대행사 OOH PM 경력 모집</span></a>
        <div class="company_nm">㈜인컴이즈 관심기업 등록</div>
      </div>
    </body></html>
    """
    site = _site("saramin_hot100", "https://www.saramin.co.kr/zf_user/jobs/hot100")
    items = saramin_hot100.parse_html(html, site, DEFAULTS)
    assert items[0].title == "[㈜인컴이즈] 광고대행사 OOH PM 경력 모집"


def test_saramin_strips_orphan_bracket_prefix():
    html = """
    <html><body>
      <div class="list_item">
        <a class="job_tit" href="/zf_user/jobs/relay/view?rec_idx=123"><span>국비] 의료데이터 기반 AI 실무자 양성과정</span></a>
        <div class="company_nm">미래융합교육원</div>
      </div>
    </body></html>
    """
    site = _site("saramin_hot100", "https://www.saramin.co.kr/zf_user/jobs/hot100")
    items = saramin_hot100.parse_html(html, site, DEFAULTS)
    assert items[0].title == "[미래융합교육원] 의료데이터 기반 AI 실무자 양성과정"


def test_saramin_normalizes_relay_detail_url():
    assert saramin_hot100._normalized_detail_url(
        "https://www.saramin.co.kr/zf_user/jobs/relay/view?view_type=list&rec_idx=53760288&referNonce=abc"
    ) == "https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=53760288"


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
    assert items[0].summary is None
    assert "jobkorea.co.kr/Recruit/GI_Read/12345" in str(items[0].url)


def test_jobkorea_detail_iframe_url_builder():
    iframe_url = jobkorea_ai._detail_iframe_url(
        "https://www.jobkorea.co.kr/Recruit/GI_Read/12345?sc=322"
    )
    assert iframe_url == (
        "https://www.jobkorea.co.kr/Recruit/GI_Read_Comt_Ifrm"
        "?sc=322&Gno=12345&isHiringCenter=false&hideMapView=false"
    )


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


def test_naver_recruit_extracts_detail_wrap_body():
    html = """
    <html><body>
      <div class="detail_wrap">
        <div class="detail_box"><h4 class="detail_title">What You'll Do</h4><p class="detail_text">모델 학습 운영</p></div>
        <div class="detail_box"><h4 class="detail_title">Required Skills</h4><p class="detail_text">Python</p></div>
      </div>
    </body></html>
    """
    body = naver_recruit.extract_body_text(html, naver_recruit.BODY_SELECTORS)
    assert body == "What You'll Do 모델 학습 운영 Required Skills Python"


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


def test_snu_cse_skips_navigation_links():
    html = """
    <html><body><ul class="notice-list">
      <li><a href="/community/notice">공지사항</a></li>
      <li><a href="/about/overview">학부 소개</a></li>
      <li><a href="/ko/community/notice/24518">정상 공지</a></li>
    </ul></body></html>
    """
    site = _site("snu_cse_notice", "https://cse.snu.ac.kr/community/notice")
    items = snu_cse_notice.parse_html(html, site, DEFAULTS)
    assert [i.title for i in items] == ["정상 공지"]


def test_snu_cse_extracts_streamed_body_payload():
    html = """
    <script>
    window.__reactRouterContext.streamController.enqueue("[{\\"loaderData\\":{}},\\"html\\",\\"\\u003cp\\u003e본문 첫줄\\u003c/p\\u003e\\u003cp\\u003e본문 둘째줄\\u003c/p\\u003e\\",\\"cssRules\\",\\"x\\"]");
    </script>
    """
    body = snu_cse_notice._extract_streamed_body(html)
    assert body and "본문 첫줄" in body and "본문 둘째줄" in body


def test_extract_detail_body_for_school_notice_layouts():
    html = """
    <html><body>
      <div class="board-view">
        <p>장학금 신청 안내</p>
        <p>신청 기한은 2026-06-01입니다.</p>
      </div>
    </body></html>
    """
    body = snu_cse_notice.extract_body_text(html, snu_cse_notice.BODY_SELECTORS)
    assert body
    assert "장학금 신청 안내" in body
    assert "2026-06-01" in body


def test_snu_cba_extracts_bbs_contents_body():
    html = """
    <html><body>
      <div class="bbs_contents">
        <p>개설과목 안내</p>
        <p>문의: 교학행정실</p>
      </div>
    </body></html>
    """
    body = snu_cba_notice.extract_body_text(html, snu_cba_notice.BODY_SELECTORS)
    assert body == "개설과목 안내 문의: 교학행정실"


def test_extract_meta_content_reads_description():
    html = '<meta name="description" content="공고 본문 요약">'
    assert saramin_hot100.extract_meta_content(html, ["description"]) == "공고 본문 요약"


if __name__ == "__main__":
    test_snu_cse_table_layout()
    test_snu_cba_basic()
    test_saramin_with_company()
    test_saramin_strips_duplicate_company_prefix_from_title()
    test_saramin_strips_orphan_bracket_prefix()
    test_saramin_normalizes_relay_detail_url()
    test_jobkorea_fragment_parses_recruit_items()
    test_jobkorea_detail_iframe_url_builder()
    test_naver_payload_basic()
    test_naver_recruit_extracts_detail_wrap_body()
    test_naver_cafe_payload_basic()
    test_naver_cafe_url_pattern_required()
    test_safe_href_filters_javascript_anchor()
    test_snu_cse_skips_navigation_links()
    test_snu_cse_extracts_streamed_body_payload()
    test_extract_detail_body_for_school_notice_layouts()
    test_snu_cba_extracts_bbs_contents_body()
    test_extract_meta_content_reads_description()
    print("all parser tests passed")

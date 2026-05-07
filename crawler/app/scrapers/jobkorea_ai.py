from __future__ import annotations

from typing import Iterable

from ..config import Defaults, SiteConfig
from ..models import RawNotice
from .base import ScrapeContext, first_text, make_notice, safe_href, take

# 잡코리아 AI잡스는 AJAX JSON으로 HTML 조각(`html` 필드)을 반환한다.
AJAX_URL = "https://www.jobkorea.co.kr/recruit/ai-jobs/GetRecruitList"


def parse_html_fragment(html: str, site: SiteConfig, defaults: Defaults) -> list[RawNotice]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    out: list[RawNotice] = []
    for it in soup.select("li.recruit-item"):
        link = it.select_one("a.recruit-link")
        if not link:
            continue
        url = safe_href(link.get("href", ""), site.url)
        if not url:
            continue
        title = first_text(link.select_one(".recruit-title .title, h3.title"))
        company = first_text(it.select_one(".company-name a, .company-name"))
        deadline = link.get("data-applyclosedt") or None
        notice = make_notice(
            site_id=site.id,
            title=f"[{company}] {title}" if company else title,
            url=url,
            summary=deadline,
        )
        if notice:
            out.append(notice)
    return take(out, defaults.max_items_per_run)


def scrape(ctx: ScrapeContext) -> Iterable[RawNotice]:
    resp = ctx.client.get(
        AJAX_URL,
        headers={
            "Referer": ctx.site.url,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json,text/plain,*/*",
        },
        params={"pageNo": 1, "pageSize": 100},
    )
    resp.raise_for_status()
    data = resp.json()
    return parse_html_fragment(data.get("html") or "", ctx.site, ctx.defaults)

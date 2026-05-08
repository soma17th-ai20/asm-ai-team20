from __future__ import annotations

from typing import Iterable

from ..config import Defaults, SiteConfig
from ..models import RawNotice
from .base import ScrapeContext, first_text, make_notice, safe_href, take


def parse_html(html: str, site: SiteConfig, defaults: Defaults) -> list[RawNotice]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    rows = soup.select("table tbody tr") or soup.select(
        "ul.board-list li, .notice-list li, li"
    )
    out: list[RawNotice] = []
    for row in rows:
        link = row.select_one("a[href]")
        if not link:
            continue
        url = safe_href(link.get("href", ""), site.url)
        if not url:
            continue
        title = first_text(link)
        date_node = row.select_one(".date, .td-date, time, td:nth-of-type(4), td:nth-of-type(5)")
        notice = make_notice(
            site_id=site.id,
            title=title,
            url=url,
            posted_at=first_text(date_node) or None,
        )
        if notice:
            out.append(notice)
    return take(out, defaults.max_items_per_run)


def scrape(ctx: ScrapeContext) -> Iterable[RawNotice]:
    resp = ctx.client.get(ctx.site.url)
    resp.raise_for_status()
    return parse_html(resp.text, ctx.site, ctx.defaults)

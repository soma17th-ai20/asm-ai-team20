from __future__ import annotations

from typing import Iterable

from ..config import Defaults, SiteConfig
from ..models import RawNotice
from .base import ScrapeContext, first_text, make_notice, safe_href, take


def parse_html(html: str, site: SiteConfig, defaults: Defaults) -> list[RawNotice]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    items = (
        soup.select(".list_item, .item_recruit, .list_body .item, .common_recruilt_list li")
        or soup.select("li:has(a[href*='/zf_user/jobs'])")
    )
    out: list[RawNotice] = []
    for item in items:
        link = item.select_one(
            "a[href*='/zf_user/jobs'], a[href*='rec_idx'], a[href]"
        )
        if not link:
            continue
        url = safe_href(link.get("href", ""), site.url)
        if not url:
            continue
        title = (
            first_text(item.select_one(".job_tit, .title, h2, .area_job .job_tit"))
            or first_text(link)
        )
        company = first_text(item.select_one(".company_nm, .corp_name, .area_corp"))
        notice = make_notice(
            site_id=site.id,
            title=f"[{company}] {title}" if company else title,
            url=url,
            summary=company or None,
        )
        if notice:
            out.append(notice)
    return take(out, defaults.max_items_per_run)


def scrape(ctx: ScrapeContext) -> Iterable[RawNotice]:
    resp = ctx.client.get(ctx.site.url)
    resp.raise_for_status()
    return parse_html(resp.text, ctx.site, ctx.defaults)

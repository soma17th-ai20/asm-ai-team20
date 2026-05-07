from __future__ import annotations

from typing import Iterable

from ..models import RawNotice
from .base import ScrapeContext, first_text, take


def scrape(ctx: ScrapeContext) -> Iterable[RawNotice]:
    soup = ctx.soup()
    items = (
        soup.select(".list_item, .item_recruit, .list_body .item, .common_recruilt_list li")
        or soup.select("li:has(a[href*='/zf_user/jobs'])")
    )
    found: list[RawNotice] = []

    for item in items:
        link = item.select_one("a[href*='/zf_user/jobs'], a[href*='rec_idx'], a[href]")
        if not link:
            continue
        href = link.get("href", "").strip()
        if not href:
            continue
        title = (
            first_text(item.select_one(".job_tit, .title, h2, .area_job .job_tit"))
            or first_text(link)
        )
        company = first_text(item.select_one(".company_nm, .corp_name, .area_corp"))
        if not title:
            continue
        summary = company or None
        found.append(
            RawNotice(
                source_id=ctx.site.id,
                title=f"[{company}] {title}" if company else title,
                url=ctx.absolute(href),
                summary=summary,
            )
        )

    return take(found, ctx.defaults.max_items_per_run)

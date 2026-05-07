from __future__ import annotations

from typing import Iterable

from ..models import RawNotice
from .base import ScrapeContext, first_text, take


def scrape(ctx: ScrapeContext) -> Iterable[RawNotice]:
    soup = ctx.soup()
    items = (
        soup.select(".lists li, .recruit-info, .list-default li, .list-item, .post")
        or soup.select("li:has(a[href*='/Recruit/'])")
    )
    found: list[RawNotice] = []

    for item in items:
        link = item.select_one("a[href*='/Recruit/'], a[href*='GI_Read'], a[href]")
        if not link:
            continue
        href = link.get("href", "").strip()
        if not href:
            continue
        title = (
            first_text(item.select_one(".title, .post-list-info .information, h2"))
            or first_text(link)
        )
        company = first_text(item.select_one(".name, .corp-name-txt, .company"))
        if not title or len(title) < 2:
            continue
        found.append(
            RawNotice(
                source_id=ctx.site.id,
                title=f"[{company}] {title}" if company else title,
                url=ctx.absolute(href),
                summary=company or None,
            )
        )

    return take(found, ctx.defaults.max_items_per_run)

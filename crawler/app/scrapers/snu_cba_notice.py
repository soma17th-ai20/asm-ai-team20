from __future__ import annotations

from typing import Iterable

from ..models import RawNotice
from .base import ScrapeContext, first_text, take


def scrape(ctx: ScrapeContext) -> Iterable[RawNotice]:
    soup = ctx.soup()
    rows = (
        soup.select(".board-list tr, .news-list li, .notice-list li, table tbody tr")
        or soup.select("li:has(a)")
    )
    found: list[RawNotice] = []

    for row in rows:
        link = row.select_one("a[href]")
        if not link:
            continue
        href = link.get("href", "").strip()
        if not href or href.startswith("#"):
            continue
        title = first_text(row.select_one(".title, .subject, strong")) or first_text(link)
        if not title or len(title) < 3:
            continue
        posted_at = first_text(row.select_one(".date, time, .reg-date"))
        found.append(
            RawNotice(
                source_id=ctx.site.id,
                title=title,
                url=ctx.absolute(href),
                posted_at=posted_at or None,
            )
        )

    return take(found, ctx.defaults.max_items_per_run)

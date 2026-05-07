from __future__ import annotations

from typing import Iterable

from ..models import RawNotice
from .base import ScrapeContext, first_text, take


def scrape(ctx: ScrapeContext) -> Iterable[RawNotice]:
    soup = ctx.soup()
    rows = soup.select("table tbody tr") or soup.select("ul.board-list li, .notice-list li, li")
    found: list[RawNotice] = []

    for row in rows:
        link = row.select_one("a[href]")
        if not link:
            continue
        href = link.get("href", "").strip()
        if not href or href.startswith("#"):
            continue
        title = first_text(link)
        if not title or len(title) < 3:
            continue
        date_node = row.select_one(".date, .td-date, time, td:nth-of-type(4), td:nth-of-type(5)")
        posted_at = first_text(date_node) or None
        found.append(
            RawNotice(
                source_id=ctx.site.id,
                title=title,
                url=ctx.absolute(href),
                posted_at=posted_at,
            )
        )

    return take(found, ctx.defaults.max_items_per_run)

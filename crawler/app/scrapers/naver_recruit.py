from __future__ import annotations

import json
import re
from typing import Iterable

from ..models import RawNotice
from .base import ScrapeContext, first_text, take

# 네이버 채용 페이지는 SPA로 렌더된다. JS 렌더링 없이 HTTP만으로 1차 시도하되,
# 실패하면 playwright 모드로 전환할 수 있도록 sites.json의 render: "playwright" 플래그를 둔다.
# 이 함수는 두 경로 모두에서 동작하는 폴백 파서다.


def scrape(ctx: ScrapeContext) -> Iterable[RawNotice]:
    soup = ctx.soup()
    found: list[RawNotice] = []

    # 1) 우선 화면에 그려진 카드 형태의 링크를 찾는다.
    cards = soup.select("a.card_link, .card_list a, a[href*='view.do'], a[href*='/rcrt/']")
    for link in cards:
        href = link.get("href", "").strip()
        if not href or href.startswith("#"):
            continue
        title = first_text(link.select_one(".card_title, .title, strong")) or first_text(link)
        if not title or len(title) < 3:
            continue
        meta = first_text(link.select_one(".card_info, .desc, .info"))
        found.append(
            RawNotice(
                source_id=ctx.site.id,
                title=title,
                url=ctx.absolute(href),
                summary=meta or None,
            )
        )

    # 2) SPA 초기 페이로드에 JSON으로 박혀있는 케이스 — window.__INITIAL_STATE__ 등.
    if not found:
        for script in soup.find_all("script"):
            text = script.string or ""
            m = re.search(r"window\.__\w+__\s*=\s*(\{.*?\});", text, re.S)
            if not m:
                continue
            try:
                payload = json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
            for entry in _walk_for_jobs(payload):
                found.append(
                    RawNotice(
                        source_id=ctx.site.id,
                        title=entry["title"],
                        url=ctx.absolute(entry["url"]),
                        summary=entry.get("summary"),
                    )
                )

    return take(found, ctx.defaults.max_items_per_run)


def _walk_for_jobs(node, out=None):
    if out is None:
        out = []
    if isinstance(node, dict):
        title = node.get("title") or node.get("annoTitle") or node.get("name")
        url = node.get("url") or node.get("detailUrl") or node.get("link")
        if title and url and isinstance(title, str) and isinstance(url, str):
            out.append({"title": title.strip(), "url": url.strip(), "summary": node.get("subTitle")})
        for v in node.values():
            _walk_for_jobs(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk_for_jobs(v, out)
    return out

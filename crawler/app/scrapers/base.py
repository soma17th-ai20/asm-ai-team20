from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from ..config import Defaults, SiteConfig
from ..models import RawNotice


@dataclass
class ScrapeContext:
    site: SiteConfig
    defaults: Defaults
    html: str

    def soup(self) -> BeautifulSoup:
        return BeautifulSoup(self.html, "lxml")

    def absolute(self, href: str) -> str:
        return urljoin(self.site.url, href)


Scraper = Callable[[ScrapeContext], Iterable[RawNotice]]


def first_text(node: Tag | None) -> str:
    if node is None:
        return ""
    return " ".join(node.get_text(" ", strip=True).split())


def take(items: Iterable[RawNotice], limit: int) -> list[RawNotice]:
    out: list[RawNotice] = []
    for item in items:
        out.append(item)
        if len(out) >= limit:
            break
    return out

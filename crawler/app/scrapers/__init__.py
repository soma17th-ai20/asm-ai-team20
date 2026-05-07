from __future__ import annotations

from typing import Callable

from .base import ScrapeContext, Scraper
from .snu_cse_notice import scrape as snu_cse_notice
from .snu_cba_notice import scrape as snu_cba_notice
from .saramin_hot100 import scrape as saramin_hot100
from .naver_recruit import scrape as naver_recruit
from .jobkorea_ai import scrape as jobkorea_ai

REGISTRY: dict[str, Scraper] = {
    "snu_cse_notice": snu_cse_notice,
    "snu_cba_notice": snu_cba_notice,
    "saramin_hot100": saramin_hot100,
    "naver_recruit": naver_recruit,
    "jobkorea_ai": jobkorea_ai,
}


def get(name: str) -> Scraper:
    if name not in REGISTRY:
        raise KeyError(f"unknown scraper: {name}")
    return REGISTRY[name]


__all__ = ["REGISTRY", "ScrapeContext", "Scraper", "get"]

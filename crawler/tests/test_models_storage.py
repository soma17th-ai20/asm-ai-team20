from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# 프로젝트 루트를 path에 추가
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import storage  # noqa: E402
from app.models import RawNotice  # noqa: E402


def _sample(url: str, title: str = "공지 제목") -> RawNotice:
    return RawNotice(source_id="snu_cse_notice", title=title, url=url)


def test_content_hash_stable():
    a = _sample("https://example.com/1")
    b = _sample("https://example.com/1")
    assert a.content_hash() == b.content_hash()


def test_content_hash_distinct_by_url():
    a = _sample("https://example.com/1")
    b = _sample("https://example.com/2")
    assert a.content_hash() != b.content_hash()


def test_dedup_on_insert():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.db"
        with storage.connect(db) as conn:
            inserted, dup = storage.insert_many(conn, [_sample("https://example.com/1")])
            assert (inserted, dup) == (1, 0)
            inserted, dup = storage.insert_many(
                conn,
                [_sample("https://example.com/1"), _sample("https://example.com/2")],
            )
            assert (inserted, dup) == (1, 1)
            assert storage.count(conn) == 2


def test_list_notices_orders_recent_first():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.db"
        with storage.connect(db) as conn:
            storage.insert_many(conn, [_sample(f"https://example.com/{i}") for i in range(3)])
            rows = storage.list_notices(conn, limit=10)
            assert len(rows) == 3
            assert rows[0].source_id == "snu_cse_notice"


if __name__ == "__main__":
    test_content_hash_stable()
    test_content_hash_distinct_by_url()
    test_dedup_on_insert()
    test_list_notices_orders_recent_first()
    print("all tests passed")

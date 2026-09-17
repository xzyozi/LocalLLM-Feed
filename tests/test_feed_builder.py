"""feed_builder モジュールの単体テスト。"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from localllm_feed import feed_builder
from localllm_feed.models import ModelRecord


def _rec(rec_id: str, d: str, params: float = 7.0) -> ModelRecord:
    return ModelRecord(id=rec_id, base=rec_id, author="a", date=d, params_b=params)


def test_purge_expired_removes_old() -> None:
    today = date(2026, 9, 17)
    records = [
        _rec("new", "2026-09-10"),
        _rec("old", "2026-07-01"),
    ]
    kept = feed_builder.purge_expired(records, retention_days=30, today=today)
    ids = {r.id for r in kept}
    assert "new" in ids
    assert "old" not in ids


def test_sort_and_truncate() -> None:
    records = [
        _rec("a", "2026-09-01"),
        _rec("b", "2026-09-15"),
        _rec("c", "2026-09-10"),
    ]
    result = feed_builder.sort_and_truncate(records, max_records=2)
    assert [r.id for r in result] == ["b", "c"]


def test_build_feed_sets_count_and_order() -> None:
    today = date(2026, 9, 17)
    records = [
        _rec("a", "2026-09-01"),
        _rec("old", "2026-01-01"),
        _rec("b", "2026-09-16"),
    ]
    feed = feed_builder.build_feed(
        records, retention_days=30, max_records=10, today=today, generated_at="2026-09-17T00:00:00Z"
    )
    assert feed.count == 2
    assert feed.models[0].id == "b"


def test_write_json_atomic_no_leftover_tmp(tmp_path: Path) -> None:
    out = tmp_path / "sub" / "models_feed.json"
    feed_builder.write_json_atomic(out, {"schema_version": 1, "models": []})
    assert out.exists()
    assert not out.with_suffix(out.suffix + ".tmp").exists()
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["schema_version"] == 1
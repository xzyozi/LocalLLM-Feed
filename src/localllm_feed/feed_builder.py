"""フィード生成（パージ・件数切り詰め・原子的書き出し）。

LLF-DS-001 §3.1（原子置換契約）・§4.1（保持期間とパージ）、
LLF-DD-001 の FeedBuilder に対応する。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path

from localllm_feed.models import FEED_SCHEMA_VERSION, ModelRecord, ModelsFeed


def purge_expired(records: list[ModelRecord], retention_days: int, today: date | None = None) -> list[ModelRecord]:
    """date が today - retention_days より古いレコードを除外する。"""
    ref = today or datetime.now(timezone.utc).date()
    cutoff = ref - timedelta(days=retention_days)
    kept: list[ModelRecord] = []
    for rec in records:
        rec_date = _parse_date(rec.date)
        if rec_date is None or rec_date >= cutoff:
            kept.append(rec)
    return kept


def sort_by_date(records: list[ModelRecord]) -> list[ModelRecord]:
    """日付降順（新しい順）にソートした新しいリストを返す。

    Args:
        records: 並べ替え対象のレコード群。

    Returns:
        date の降順に並べ替えたリスト（入力は変更しない）。
    """
    return sorted(records, key=lambda r: r.date, reverse=True)


def truncate(records: list[ModelRecord], max_records: int) -> list[ModelRecord]:
    """先頭 max_records 件へ切り詰める。

    Args:
        records: 切り詰め対象のレコード群。
        max_records: 残す最大件数。負値なら切り詰めない（全件返す）。

    Returns:
        先頭 max_records 件のリスト。max_records が負なら入力と同じ内容。
    """
    if max_records < 0:
        return list(records)
    return records[:max_records]


def sort_and_truncate(records: list[ModelRecord], max_records: int) -> list[ModelRecord]:
    """日付降順にソートし max_records 件へ切り詰める（sort_by_date + truncate の合成）。

    Args:
        records: 対象レコード群。
        max_records: 残す最大件数。負値なら切り詰めない。

    Returns:
        整形済みのレコードリスト。
    """
    return truncate(sort_by_date(records), max_records)


def build_feed(
    records: list[ModelRecord],
    retention_days: int,
    max_records: int,
    today: date | None = None,
    generated_at: str | None = None,
) -> ModelsFeed:
    """収集レコードからパージ・整形済みの ModelsFeed を構築する。"""
    kept = purge_expired(records, retention_days, today=today)
    kept = sort_and_truncate(kept, max_records)
    now = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return ModelsFeed(
        schema_version=FEED_SCHEMA_VERSION,
        generated_at=now,
        count=len(kept),
        models=kept,
    )


def write_json_atomic(path: Path | str, payload: object) -> None:
    """JSON を原子的に書き出す（tmp へ全量書き→fsync→os.replace）。

    LLF-DS-001 §3.1。置換前に例外が出ても既存の正本は破壊しない。
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)
        fp.flush()
        os.fsync(fp.fileno())
    os.replace(tmp, target)


def write_feed(path: Path | str, feed: ModelsFeed) -> None:
    """ModelsFeed を models_feed.json として原子的に書き出す。"""
    write_json_atomic(path, feed.model_dump())


def _parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None

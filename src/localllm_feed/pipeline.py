"""パイプライン実行エントリポイント（LLF-DD-001 §3.1）。

python -m localllm_feed.pipeline で実行する。
収集 → TL;DR 付与 → フィード生成（原子的書き出し） → 人気配布者スキャン →
候補の JSON 出力（Issue 通知はワークフロー側が担当）。

失敗契約（LLF-DD-001 §3.4）:
- フィード生成失敗時は既存の models_feed.json を破壊しない（原子置換の性質）。
- スキャン/候補出力の失敗はフィード生成の成否に影響させず、警告として扱う。
"""

from __future__ import annotations

import os
from pathlib import Path
import sys

from localllm_feed import hf_crawler
from localllm_feed.config import (
    DEFAULT_COLLECTION_PATH,
    DEFAULT_SCORING_PATH,
    load_collection_config,
)
from localllm_feed.feed_builder import (
    build_feed,
    purge_expired,
    sort_and_truncate,
    write_feed,
    write_json_atomic,
)
from localllm_feed.scoring_export import DEFAULT_SCORING_JSON, export_scoring_json

FEED_OUTPUT = Path("public/data/models_feed.json")
CANDIDATES_OUTPUT = Path("public/data/popular_candidates.json")


def run(
    collection_path: Path | str = DEFAULT_COLLECTION_PATH,
    scoring_path: Path | str = DEFAULT_SCORING_PATH,
    feed_output: Path | str = FEED_OUTPUT,
    scoring_json: Path | str = DEFAULT_SCORING_JSON,
    candidates_output: Path | str = CANDIDATES_OUTPUT,
    token: str | None = None,
) -> int:
    """パイプラインを実行し、生成件数を標準出力に示して 0/1 を返す。"""
    config = load_collection_config(collection_path)
    client = hf_crawler.HuggingFaceClient(token=token or os.environ.get("HF_TOKEN"))
    try:
        summaries = hf_crawler.crawl_models(client, config)
        records = hf_crawler.summaries_to_records(summaries)
        # パージ→日付降順ソート→件数切り詰めの後、上位に README 由来の TL;DR を付与
        records = purge_expired(records, config.retention_days)
        records = sort_and_truncate(records, config.max_records)
        records = hf_crawler.enrich_with_tldr(client, records, config.tldr_fetch_limit)
        feed = build_feed(records, config.retention_days, config.max_records)
        write_feed(feed_output, feed)
        tldr_count = sum(1 for m in feed.models if m.tldr)
        print(f"[feed] {feed.count} records ({tldr_count} with TL;DR) -> {feed_output}")

        # スコアリング設定の JSON 化（フロント配信用）
        export_scoring_json(scoring_path, scoring_json)
        print(f"[scoring] -> {scoring_json}")

        # 人気配布者スキャン（失敗しても全体は継続）
        try:
            candidates = hf_crawler.scan_popular_outside_whitelist(client, config)
            write_json_atomic(candidates_output, [c.model_dump() for c in candidates])
            print(f"[scan] {len(candidates)} candidate authors -> {candidates_output}")
        except Exception as exc:  # noqa: BLE001 - 通知系は警告扱い
            print(f"[scan] WARNING: popular scan failed: {exc}", file=sys.stderr)
    finally:
        client.close()
    return 0


def main() -> int:
    try:
        return run()
    except Exception as exc:  # noqa: BLE001 - トップレベルで失敗を要約
        print(f"[pipeline] ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

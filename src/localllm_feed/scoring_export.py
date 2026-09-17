"""scoring.toml を public/data/scoring.json へ変換する（LLF-DD-001 ScoringConverter）。

フロントで TOML パーサへ依存しないよう、ビルド時に JSON 化して配信する。
"""

from __future__ import annotations

from pathlib import Path

from localllm_feed.config import load_scoring_config
from localllm_feed.feed_builder import write_json_atomic

DEFAULT_SCORING_JSON = Path("public/data/scoring.json")


def export_scoring_json(
    scoring_toml: Path | str,
    out_path: Path | str = DEFAULT_SCORING_JSON,
) -> dict:
    """scoring.toml を読み込み scoring.json として原子的に書き出す。"""
    config = load_scoring_config(scoring_toml)
    write_json_atomic(out_path, config)
    return config
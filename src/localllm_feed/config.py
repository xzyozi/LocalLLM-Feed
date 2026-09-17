"""設定ファイル（collection.toml / scoring.toml）のローダ。

Python 3.11+ 標準の tomllib を使用する。値の正本は
docs/design/LLF-DS-001 §2.3（収集）および LLF-SC-001 §2（スコアリング）。
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_COLLECTION_PATH = Path("config/collection.toml")
DEFAULT_SCORING_PATH = Path("config/scoring.toml")


@dataclass(frozen=True)
class PopularScanConfig:
    """ホワイトリスト外の人気配布者検出設定。"""

    enabled: bool = True
    notify_min_downloads: int = 1000
    scan_limit: int = 100


@dataclass(frozen=True)
class CollectionConfig:
    """収集条件（collection.toml）。"""

    retention_days: int = 30
    max_records: int = 300
    min_downloads: int = 50
    gguf_only: bool = True
    authors: tuple[str, ...] = ()
    popular_scan: PopularScanConfig = field(default_factory=PopularScanConfig)


def load_collection_config(path: Path | str = DEFAULT_COLLECTION_PATH) -> CollectionConfig:
    """collection.toml を読み込み CollectionConfig を返す。

    未知キーは無視する。必須セクション欠落時は既定値で補完する（LLF-DS-001 §4.2）。
    """
    data = _read_toml(path)
    collection = data.get("collection", {})
    scan = data.get("popular_scan", {})

    return CollectionConfig(
        retention_days=int(collection.get("retention_days", 30)),
        max_records=int(collection.get("max_records", 300)),
        min_downloads=int(collection.get("min_downloads", 50)),
        gguf_only=bool(collection.get("gguf_only", True)),
        authors=tuple(collection.get("authors", ())),
        popular_scan=PopularScanConfig(
            enabled=bool(scan.get("enabled", True)),
            notify_min_downloads=int(scan.get("notify_min_downloads", 1000)),
            scan_limit=int(scan.get("scan_limit", 100)),
        ),
    )


def load_scoring_config(path: Path | str = DEFAULT_SCORING_PATH) -> dict:
    """scoring.toml を読み込み dict として返す。

    配点数値の解釈はフロント（および scoring.json 変換）が行うため、
    ここでは構造をそのまま辞書で返す。
    """
    return _read_toml(path)


def _read_toml(path: Path | str) -> dict:
    with open(path, "rb") as fp:
        return tomllib.load(fp)
"""LocalLLM Feed のデータモデル・DTO 定義。

配信フィード（models_feed.json）と収集設定（collection.toml）の
スキーマを pydantic で定義する。スコアリング配点は LLF-SC-001 を正本とし、
フロント側で消費するためここでは扱わない。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

FEED_SCHEMA_VERSION = 1


class ModelRecord(BaseModel):
    """配信フィードの単一モデルレコード（LLF-DS-001 §2.2）。"""

    id: str
    base: str
    author: str
    date: str
    params_b: float
    is_distilled: bool = False
    quants: list[str] = Field(default_factory=list)
    downloads: int = 0
    tldr: str = ""


class ModelsFeed(BaseModel):
    """配信フィードファイル全体（LLF-DS-001 §2.2）。"""

    schema_version: int = FEED_SCHEMA_VERSION
    generated_at: str
    count: int
    models: list[ModelRecord] = Field(default_factory=list)


class CandidateAuthor(BaseModel):
    """ホワイトリスト外の人気配布者候補（LLF-DS-001 §2.5）。"""

    author: str
    downloads: int
    sample_model_id: str

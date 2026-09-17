"""LocalLLM Feed バックエンドパッケージ。

HF API からファクトを抽出し public/data/models_feed.json を生成する。
スコアの決定はフロント（LLF-SC-001）に委譲する分離アーキテクチャ（LLF-BD-001）。
"""

__version__ = "0.1.0"

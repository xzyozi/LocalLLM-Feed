# LocalLLM Feed 🦙

> **ローカルLLM＆GGUF特化型 新着TL;DRフィード（GitHub Actions + GitHub Pages 完結・ゼロインフラ）**

[English](./README.md) | [日本語](./README.ja.md)

Hugging Face 上の GGUF モデル動向を毎日収集し、ユーザーのハードウェア環境（VRAM）とユースケース（速度/精度）に最適なモデルをノイズレスに発見・導入するための静的フィードプラットフォームです。

## 特徴

- **ファクト収集とスコアリングの分離**: バックエンド（GitHub Actions）はパラメータ数・量子化形式・蒸留有無などの「事実」だけを抽出。スコアの決定はフロント（GitHub Pages）が動的に行う。
- **クライアントサイド動的スコアリング**: ブラウザ上で VRAM 設定に応じて Total Score を再計算・ソート（DB/APIサーバー不要）。
- **ローカル環境へのエクスポート**: 選択モデルの Bash 環境変数（`n_gpu_layers` 初期値を自動算出）や Ollama Modelfile をワンクリックコピー。
- **ゼロインフラ運用**: GitHub Actions と Pages のみで完結。ランニングコストなし。

## アーキテクチャ

```
Hugging Face API
      │ (毎日1回 / GitHub Actions)
      ▼
収集(HuggingFaceCrawler) → TL;DR抽出(ルールベース) → フィード生成(FeedBuilder)
      │
      ▼
public/data/models_feed.json  ──(GitHub Pages)──▶  ブラウザ(動的スコアリング・検索・エクスポート)
```

- 詳細は [基本設計書](./docs/design/LLF-BD-001_基本設計書.md)、[詳細設計書](./docs/design/LLF-DD-001_詳細設計書.md)、[データ構造仕様書](./docs/design/LLF-DS-001_データ構造仕様書.md)、[スコアリング設定仕様書](./docs/design/LLF-SC-001_スコアリング設定仕様書.md) を参照。

## 設定

収集条件とスコアリング配点は `config/` の TOML で調整できます（コード変更不要）。

- `config/collection.toml`: 収集対象の著者ホワイトリスト、保持期間、DL下限、人気配布者スキャン設定。
- `config/scoring.toml`: VRAM 区分ごとの配点、量子化ボーナス、`n_gpu_layers` 算出係数。

## 開発

本プロジェクトは [uv](https://docs.astral.sh/uv/) を使用します。

```bash
# 依存インストール
uv pip install -e ".[dev]"

# パイプラインのローカル実行（HF API へアクセスします）
python -m localllm_feed.pipeline

# リント・型チェック・テスト
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

生成物 `public/data/models_feed.json` が更新され、GitHub Pages で配信されます。

## ライセンス

[MIT](./LICENSE)
# ScholarRepo-Finder 🔍📚
> **学術研究・アルゴリズム検証用OSS特化型 検索・探索エンジン (GitHub Pages & Markdown エクスポート対応)**

[English](./README.md) | [日本語](./README.ja.md)

[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Live%20Demo-brightgreen?logo=github)](https://xzyozi.github.io/ScholarRepo-Finder/)
[![CI](https://github.com/xzyozi/ScholarRepo-Finder/actions/workflows/ci.yml/badge.svg)](https://github.com/xzyozi/ScholarRepo-Finder/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

🌐 **Webサイト (Live Demo)**: [https://xzyozi.github.io/ScholarRepo-Finder/](https://xzyozi.github.io/ScholarRepo-Finder/)

ScholarRepo-Finder は、GitHub の膨大なリポジトリ群から **「学術的文脈を持つ」「堅牢な構造を持つ」「信頼できる開発者によって作成された」** シミュレーションおよびアルゴリズム検証用 OSS を自動抽出し、**GitHub Pages 上で完全無料・保守フリー・ゼロインフラで高速検索し、Markdown形式でワンクリック出力できる静的Webプラットフォーム** です。

---

## 🌟 主な特徴

- **完全サーバーレス・ゼロインフラ**: 外部データベースや常時稼働サーバーを全廃。GitHub Actions による定期自動クロール＆ビルドと、GitHub Pages による静的配信で完全完結。
- **データ厳選・超軽量設計**: 高スコア（厳選基準クリア）のリポジトリのみをインデックス化。データ容量を数MB以内に抑え、ブラウザ上での瞬時ロードを実現。
- **多角的スコアリング**: コメント可能なTOMLプロファイルにより、再利用可能な提供形態、公開API、モジュール境界、利用手順、再現可能な選定根拠を評価。
- **爆速クライアント検索**: ブラウザ内のインメモリ検索エンジン（MiniSearch）により、言語・スコア・論文有無でのファセット絞り込みが待ち時間ゼロ（0ms）で動作。
- **Markdown ワンクリック出力**: 絞り込んだ検索結果を一括で Markdown ファイル（`.md`）としてダウンロード、または個別カードを Markdown 引用形式でクリップボードへコピー可能（Obsidian, Notion, 論文執筆ノートにそのまま活用可能）。

---

## 📐 アーキテクチャ概要

```mermaid
flowchart LR
    A[GitHub / Papers with Code API] --> B[GitHub Actions バッチ収集]
    B --> C[特徴抽出 & 多角スコアリング]
    C --> D[データ軽量化 & 静的JSONビルド]
    D --> E[GitHub Pages デプロイ]
    E --> F[ブラウザ内 高速ファセット検索 UI]
    F --> G[Markdown エクスポート / 引用コピー]
```

詳細な設計については以下をご参照ください：
- 📘 [基本設計書 (SRF-BD-001)](./docs/design/SRF-BD-001_基本設計書.md)
- 📊 [データ構造・状態設計書 (SRF-DS-001)](./docs/design/SRF-DS-001_データ構造仕様書.md)
- ⚙️ [詳細設計書 (SRF-DD-001)](./docs/design/SRF-DD-001_詳細設計書.md)

---

## 🚀 クイックスタート

### 前提条件
- Python 3.11 以上
- [uv](https://github.com/astral-sh/uv) (推奨パッケージマネージャー)

### インストール & 開発
```bash
# 依存パッケージの同期
uv sync

# パイプラインのローカルテスト実行
uv run python -m scholarrepo_finder.pipeline

# リント・テスト実行
uv run ruff check .
uv run mypy .
uv run pytest
```

---

## 📄 ライセンス
本プロジェクトは [MIT License](./LICENSE) のもとで公開されています。

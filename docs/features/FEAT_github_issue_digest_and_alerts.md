---
title: "GitHub Issue 連携機能 アイデア・仕様検討書"
document_type: "feature_idea"
version: "1.0"
created_at: "2026-08-31"
updated_at: "2026-08-31"
author: "ScholarRepo-Finder 開発チーム"
purpose: "GitHub Actions クロール結果を GitHub Issues に自動起票し、新着学術OSSの通知および研究メモ・再現実験ログのストック基盤として活用するためのアイデア・仕様案を整理するため"
related_documents:
  - "docs/design/SRF-BD-001_基本設計書.md"
  - "docs/design/SRF-DD-001_詳細設計書.md"
---

# 機能アイデア検討書：GitHub Issue 連携 (Weekly Digest & 高スコア速報)

| 項目       | 内容                                               |
| :--------- | :------------------------------------------------- |
| 文書番号   | SRF-FEAT-001                                       |
| 機能名     | GitHub Issue 連携による学術OSS通知・研究ノート機能 |
| ステータス | アイデア検討中 (Proposed / Backlog)                |
| 作成日     | 2026-08-31                                         |
| 作成者     | ScholarRepo-Finder 開発チーム                      |

---

## 1. 概要と背景

### 1.1 背景
ScholarRepo-Finder では、GitHub Pages（Web UI）上で高速なファセット検索および Markdown 一括ダウンロードを提供しているが、ユーザーが「能動的にサイトを訪問しないと新着の優良OSSに気づけない」という課題がある。

### 1.2 本機能の目的
GitHub の標準機能である **GitHub Issues** を活用し、クロールパイプライン（GitHub Actions）で新たに発見された優良リポジトリを自動起票することで、**「プッシュ通知の受信」** および **「Issue コメント欄を活用した再現実験・研究ノートの蓄積」** を実現する。

---

## 2. ユースケースと提供価値

```mermaid
flowchart TD
    Actions["GitHub Actions / 定期クロール"] -->|新着OSS検出| Judgement{"スコア・頻度判定"}

    Judgement -->|"パターンA: 週次まとめ"| WeeklyIssue["Weekly Digest Issue 自動起票<br>- 週刊 学術OSSランキング<br>- トピック別まとめ"]
    Judgement -->|"パターンB: 超高スコア Score>=85"| AlertIssue["高スコア速報 Issue 自動起票<br>- 個別リポジトリ詳細<br>- 論文リンク / 構造ハイライト"]

    WeeklyIssue --> UserNotify(("GitHub 通知 / メール"))
    AlertIssue --> UserNotify

    AlertIssue --> NoteTaking["Issue コメント欄での研究ノート蓄積<br>- 再現実験コマンドログ<br>- パラメータ検証メモ<br>- 派生論文のリンク"]
```

### 2.1 主な提供価値
1. **GitHub ネイティブな通知連携 (Watch / Subscribe)**:
   - リポジトリを Watch しておくだけで、新着の優良学術OSSが発見された際にメールやモバイルアプリへ自動通知。
2. **研究メモ・再現実験ログのストック (Discussions in Issues)**:
   - 発見されたリポジトリごとに、コメント欄で「実際に手元で動かした結果」「Docker 環境構築の知見」「ベンチマーク結果」をディスカッション・記録可能。
3. **GitHub Labels によるスマート分類**:
   - `topic:vrp`, `topic:reinforcement-learning`, `score:85+`, `lang:python` などのラベルを自動付与し、GitHub 標準の Issue 検索・フィルタリングを活用可能。

---

## 3. 起票方式の仕様案（2つのパターン）

### パターン A: Weekly Digest Issue（週刊まとめダイジェスト）
- **トリガー**: 毎週月曜日の定期クロール完了時
- **起票条件**: 過去1週間に新規インデックスされた、または大幅に更新されたリポジトリ群
- **メリット**: Issue の乱立・通知スパムを防ぎ、定期購読マガジン感覚で閲覧可能。

**【Issue 本文テンプレート案】**
```markdown
# 📚 [ScholarRepo-Finder] Weekly 学術OSSダイジェスト (2026-W35)

今週新たに発見・高評価された学術研究・アルゴリズム検証用OSSの一覧です。

### 🏆 今週の注目リポジトリ (Top Scores)
| リポジトリ                                  | 総合スコア |  言語  |        論文/DOI         | 概要                                     |
| :------------------------------------------ | :--------: | :----: | :---------------------: | :--------------------------------------- |
| [lab/vrp-rl-solver](https://github.com/...) |  **88.0**  | Python | [arXiv:2405.xxxxx](...) | 強化学習を用いた大規模配車最適化ソルバー |
| [team/discrete-sim](https://github.com/...) |  **84.5**  |  Rust  | [DOI:10.1016/...](...)  | 高速離散事象シミュレーション基盤         |

### 🏷️ カテゴリ別ピックアップ
- **Operations Research / 最適化**: `lab/vrp-rl-solver`, `...`
- **Simulation / マルチエージェント**: `team/discrete-sim`, `...`

---
*詳細なファセット検索や Markdown ダウンロードは [ScholarRepo-Finder Web](https://xzyozi.github.io/ScholarRepo-Finder/) をご利用ください。*
```

---

### パターン B: High-Score Alert Issue（超厳選リポジトリの個別速報）
- **トリガー**: 定期クロール時
- **起票条件**: $	ext{Total Score} \ge 85.0$ かつ論文リンク（DOI/arXiv）が存在する「超優良リポジトリ」のみ
- **メリット**: 1リポジトリ1 Issue となるため、個別の研究ノート・ディスカッションスレッドとして直接利用可能。
- **スパム防止**: スコア閾値を 85 点以上に高く設定し、起票件数を月数件〜十数件程度に厳選。

**【Issue 本文テンプレート案】**
```markdown
# [OSS速報] lab/vrp-rl-solver (Score: 88.0)

### 📌 リポジトリ情報
- **URL**: https://github.com/lab/vrp-rl-solver
- **著者/組織**: AI Optimization Lab (Verified Org / .edu)
- **主要言語**: Python
- **ライセンス**: MIT License
- **論文/学術リンク**: [arXiv:2405.xxxxx](https://arxiv.org/abs/2405.xxxxx)

### 📊 スコア内訳
- **構造スコア**: 45/50 (src/tests/docs分離, networkx/numpy使用, CI完備)
- **文脈スコア**: 40/50 (論文リンク明記, benchmarkキーワード高頻度)
- **著者乗数**: 1.3x (Verified Organization)
- **総合スコア**: **88.0**

### 📝 リポジトリ概要
> A deep reinforcement learning framework for solving large-scale Capacitated Vehicle Routing Problems (CVRP). Includes benchmark datasets and baseline comparisons.

---
<!-- ここに手元での検証ログやメモをコメントとして追記してください -->
```

---

## 4. 実装アプローチ

### 使用技術
- **GitHub CLI (`gh issue create`)**:
  GitHub Actions ワークフロー内で `GITHUB_TOKEN` 権限を用いてシェルから直接起票。
- または **Python GitHub API (`PyGithub` / `httpx`)**:
  ビライザーモジュールから REST API で起票。

### ワークフロー組み込みイメージ
```yaml
- name: Create Weekly Digest Issue
  if: steps.crawl.outputs.new_repos_count > 0
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    gh issue create       --title "📚 [Weekly Digest] $(date +'%Y-%m-%d') 学術OSS新着まとめ"       --body-file docs/latest_weekly_digest.md       --label "weekly-digest,automated"
```

---

## 5. 今後の検討事項
1. **起票頻度のチューニング**: 週次ダイジェスト（パターンA）を基本とし、運用フィードバックを見ながら個別速報（パターンB）を検討する。
2. **重複起票防止**: すでに過去の Issue で紹介済みのリポジトリはスキップするキャッシュ管理。

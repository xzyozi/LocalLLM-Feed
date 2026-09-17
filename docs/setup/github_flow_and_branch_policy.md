# GitHub Flow 運用規約 ＆ ブランチ自動管理ガイド

本ドキュメントは、本プロジェクトにおける **GitHub Flow（`main` 一本化）運用ルール**、および **GitHub / CI/CD / ローカル Git** を活用したブランチの自動クリーンアップ・管理仕様を定義します。

---

## 1. ブランチ戦略 (GitHub Flow 概要)

個人開発および小規模・俊敏な開発を最大化するため、二重PRのオーバーヘッドを排除した **GitHub Flow** を採用しています。

### 主要ブランチ (Long-lived Branch)
- **`main`**: 本番環境兼ベースブランチ。常時デプロイ可能・最新の安定したコードを保持します。`main` へのマージと同時に GitHub Pages が自動更新されます。

### 作業ブランチ (Short-lived Branches)
- **`feat/<機能名>`**: 新機能開発用ブランチ。`main` から分岐し、`main` へ直接 PR を作成してマージします。
- **`fix/<修正内容>`**: バグ修正用ブランチ。`main` から分岐し、`main` へマージします。
- **`docs/<内容>`**: ドキュメント作成・更新用ブランチ。
- **`chore/<内容>`**: 設定変更・依存関係更新・リファクタリング用ブランチ。

---

## 2. CI/CD ＆ リモート自動化 (GitHub / GitHub Actions)

不要なリモートブランチが残留しないよう、以下の自動化を組み込んでいます。

### ① GitHub 設定: PRマージ後のリモートブランチ自動削除
- GitHubの管理画面 (`Settings` > `General` > `Pull Requests`) にて **`Automatically delete head branches`** を有効化。
- PRが `main` にマージされた時点で、リモートの作業ブランチが自動削除されます。

---

## 3. ローカル Git 開発環境の自動化設定

リモートで削除されたブランチがローカル環境に古い追跡情報 (`[gone]`) として残るのを防ぐため、以下の設定を推奨します。

### ① `git fetch` への自動 Prune 設定
以下のコマンドを実行すると、`git fetch` や `git pull` を行うたびに、リモートで消えたブランチのローカル追跡情報を自動的に削除します。

```bash
git config --global fetch.prune true
```

### ② ローカル `[gone]` ブランチを一括削除する Git エイリアス
追跡元リモートブランチが消えたローカルブランチを一括で整理・削除するコマンドを追加します。

```bash
# エイリアスの設定 (PowerShell / Git Bash 共通)
git config --global alias.cleanup "!git branch -vv | grep '\[gone\]' | awk '{print $1}' | xargs -r git branch -d"
```

#### 使い方
```bash
git cleanup
```
実行すると、リモートで既にマージ・削除されたローカルブランチが一括で安全に削除されます。

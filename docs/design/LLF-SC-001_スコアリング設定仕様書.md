---
title: "ローカルLLM＆GGUF特化型 新着TL;DRフィード スコアリング設定仕様書"
document_type: "scoring_specification"
version: "1.0"
created_at: "2026-09-17"
updated_at: "2026-09-17"
author: "開発チーム"
purpose: "フロントエンドがクライアントサイドで動的に算出するTotal Scoreの配点テーブル（VRAMマッチング・量子化・効率ボーナス）、およびオフロードレイヤー数の算出式を定義し、config/scoring.toml の初期値仕様の正本とするため"
related_documents:
  - "LLF-BD-001 基本設計書"
  - "LLF-DD-001 詳細設計書"
  - "LLF-DS-001 データ構造仕様書"
---

# スコアリング設定仕様書（配点・算出ロジック定義）

**ローカルLLM＆GGUF特化型 新着TL;DRフィード / 動的スコアリング配点とオフロード算出**

| 項目           | 内容                                                             |
| :------------- | :--------------------------------------------------------------- |
| 文書番号       | LLF-SC-001                                                       |
| ドキュメント名 | ローカルLLM＆GGUF特化型 新着TL;DRフィード スコアリング設定仕様書 |
| 版数           | Rev.1.0                                                          |
| 作成日         | 2026-09-17                                                       |

---

## 1. 概要と設計方針

### 1.1 目的

本書は、フロントエンド（JavaScript）が `models_feed.json` の各レコードに対して算出する
**Total Score** の配点ルールと、エクスポート時の `n_gpu_layers` 算出式を定義する。
値は `config/scoring.toml` に外出しし、コード変更なしで調整可能とする（LLF-DS-001 §2.4）。

### 1.2 スコアリングの原則

- スコア計算は**フロントのインメモリ**で行う（バックエンドはスコアを持たない）。
- ユーザー設定（VRAM区分・優先度）の変更ごとに**全件を再計算**して降順ソートする。
- 本書の数値は初期値（v1）。実運用のチューニングは `scoring.toml` を編集して行い、`profile.version` を更新する。

### 1.3 Total Score の構成

```
Total Score = VRAMマッチング得点
            + 量子化フォーマット得点
            + 効率ボーナス（蒸留 × 速度優先時）
```

負値（ペナルティ）も許容し、下限は0でクランプする。

---

## 2. 設定スキーマ（config/scoring.toml）

```toml
schema_version = 1

[profile]
id = "gguf-feed-v1"
version = 1

# ユーザーVRAM区分（GB）ごとの、モデルパラメータ帯への加点/減点
# 行: ユーザーVRAM区分 / 列: モデルの params_b 帯
[vram_match]
# params 帯の境界（B）。以下 tiers で <=3B, <=8B, <=14B, <=24B, <=35B に区分
param_tiers = [3, 8, 14, 24, 35]

[vram_match.gb8]   # VRAM 8GB
scores = [8, 10, 4, -6, -12]
[vram_match.gb12]  # VRAM 12GB
scores = [4, 10, 10, -2, -8]
[vram_match.gb16]  # VRAM 16GB
scores = [2, 8, 10, 6, -4]
[vram_match.gb24]  # VRAM 24GB
scores = [0, 4, 8, 10, 6]
[vram_match.gb32]  # VRAM 32GB+
scores = [0, 2, 6, 10, 10]

[quantization]
# 量子化フォーマットが quants に含まれる場合の一律加点
sweet_spot = ["Q4_K_M", "Q5_K_M"]  # 実用性の高い定番
sweet_spot_bonus = 6.0
# 特大VRAM（32GB+）でのみ無劣化寄りフォーマットを優遇
high_fidelity = ["Q8_0", "Q6_K"]
high_fidelity_bonus = 5.0
high_fidelity_min_vram_gb = 32

[efficiency]
# is_distilled かつ 優先度=speed のときの加点
distilled_speed_bonus = 5.0

[offload]
# n_gpu_layers 初期値算出のための係数（§4）
safety_margin = 0.9        # 使用可能VRAMに掛ける安全係数
os_reserved_gb = 1.0       # OS/その他が使うVRAMの控除
kv_cache_gb = 1.5          # KVキャッシュ等の追加控除の目安
bytes_per_param_q4 = 0.5   # Q4系: 約4.5bit/param ≈ 0.5〜0.56 GB/B（概算0.5）
default_layers_35b = 40    # 35B級の代表レイヤー数（total_layers 推定の既定）
```

---

## 3. 配点仕様（VRAMマッチング・量子化・効率）

### 3.1 VRAMマッチング得点

`vram_match.<区分>.scores` は `param_tiers` に対応した配列。モデルの `params_b` が
どの帯に入るかで加点/減点を引く（論点5の5区分）。

| ユーザーVRAM \ paramsB帯 | ≤3B | ≤8B | ≤14B | ≤24B | ≤35B |
| :----------------------- | :--: | :--: | :--: | :--: | :--: |
| 8GB                      |  8   |  10  |  4   |  -6  | -12  |
| 12GB                     |  4   |  10  |  10  |  -2  |  -8  |
| 16GB                     |  2   |  8   |  10  |  6   |  -4  |
| 24GB                     |  0   |  4   |  8   |  10  |  6   |
| 32GB+                    |  0   |  2   |  6   |  10  |  10  |

- 意図: 各VRAM帯で「快適に動く最大クラス」に最大点、明らかに載らない特大モデルに強い減点。
- `params_b` が最大帯（35B）を超える場合は最終列の値を適用する。

### 3.2 量子化フォーマット得点

- `quants` に `sweet_spot`（`Q4_K_M`/`Q5_K_M`）のいずれかが含まれれば `sweet_spot_bonus`（+6）を一律加算。
- ユーザーVRAMが `high_fidelity_min_vram_gb`（32GB）以上で、`quants` に `high_fidelity`（`Q8_0`/`Q6_K`）が含まれれば `high_fidelity_bonus`（+5）を追加加算。
- 複数該当時も各カテゴリの加点は1回のみ（重複加算しない）。

### 3.3 効率ボーナス

- `is_distilled == true` かつ ユーザー優先度 `speed` のとき `distilled_speed_bonus`（+5）を加算。
- 優先度 `accuracy` のときは加算しない。

### 3.4 算出例

VRAM24GB・優先度speed・`params_b=32`（≤35B帯）・`quants=["Q4_K_M","Q8_0"]`・`is_distilled=true`:

```
VRAMマッチング(24GB, ≤35B帯) = 6
量子化(sweet_spot: Q4_K_M)   = +6
高忠実度(Q8_0だがVRAM<32)    = +0
効率(distilled × speed)      = +5
------------------------------------
Total Score = 17
```

---

## 4. オフロードレイヤー数（n_gpu_layers）算出式

エクスポート時、フロントJSが軽量な四則演算で初期値を提示する（Actions負荷なし）。

### 4.1 モデル総サイズの概算

```
model_size_gb ≈ params_b × bytes_per_param_q4
              （Q4系のとき bytes_per_param_q4 = 0.5）
```

### 4.2 使用可能VRAMの概算

```
usable_vram_gb = (vram_gb - os_reserved_gb - kv_cache_gb) × safety_margin
```

### 4.3 オフロード可能レイヤー数

```
total_layers   ≈ モデルのレイヤー数（メタから取得。不明なら default_layers_35b を params 比でスケール）
gb_per_layer   = model_size_gb / total_layers
n_gpu_layers   = floor( usable_vram_gb / gb_per_layer )
（0 未満は 0、total_layers 超は total_layers にクランプ）
```

### 4.4 算出例

VRAM24GB・`params_b=32`・`total_layers=64` の場合:

```
model_size_gb  = 32 × 0.5 = 16.0
usable_vram_gb = (24 - 1.0 - 1.5) × 0.9 = 19.35
gb_per_layer   = 16.0 / 64 = 0.25
n_gpu_layers   = floor(19.35 / 0.25) = 77 → 64 にクランプ（全層GPU）
```

VRAM8GB・同モデルの場合:

```
usable_vram_gb = (8 - 1.0 - 1.5) × 0.9 = 4.95
n_gpu_layers   = floor(4.95 / 0.25) = 19（部分オフロード）
```

---

## 5. 互換性・変更管理

- 配点や係数を変更した場合は `scoring.toml` の `profile.version` をインクリメントする。
- `schema_version` はキー構造の破壊的変更時のみ更新する。
- フロントは未知キーを無視し、必須配点欠落時は本書の初期値にフォールバックする。
- `bytes_per_param_q4` はQ4系を基準にした概算。将来的に量子化ビット別の係数へ拡張する場合は `[offload]` に追加する。

---

## 6. 改訂履歴 (Change Log)

| 版数    | 改訂日     | 変更者     | 変更内容・変更理由 (Why) |
| :------ | :--------- | :--------- | :----------------------- |
| Rev.1.0 | 2026-09-17 | 開発チーム | 新規作成（初版制定）     |
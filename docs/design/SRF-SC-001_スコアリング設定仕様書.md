# SRF-SC-001 スコアリング設定仕様書

- **文書番号**: SRF-SC-001
- **作成日**: 2026-08-31
- **ステータス**: 実装済み (Implemented)
- **対象**: `config/scoring.toml`, `scoring_config.py`, `scorer.py`, `pipeline.py`, `builder.py`

## 1. 目的と単一設定源

評価に用いる配点、上限、ハードフィルター、掲載閾値、信頼度乗数は、リポジトリ管理する `config/scoring.toml` を唯一の設定源とする。Python 3.11以上の標準ライブラリ `tomllib` で読み込むため、追加依存は不要である。TOMLのコメントには、配点の判断理由や変更時の注意点を記載する。

設定読込時に未知キー、必須キー欠落、数値範囲外、評価軸の上限超過、またはTOML構文エラーを検出した場合、評価処理は開始しない。暗黙の既定値へのフォールバックは行わない。

## 2. 設定ファイル形式

```toml
# 配点の変更理由は値の近くに記録する。
schema_version = 1
indexing_threshold = 60.0 # 掲載判定はこの値以上

[profile]
id = "reusability-v1"
version = 1

[hard_filters]
max_inactive_years = 5
min_readme_char_length = 100

[scores.reusability]
maximum = 30.0

[scores.reusability.delivery_form]
library = 12.0             # 他プログラムから直接利用できる
modular_application = 8.0  # 再利用可能なモジュールを確認できる
executable_application = 2.0 # 除外せず、優先度の差として扱う
unknown = 0.0              # 根拠不足では加点しない

[scores.reusability.public_api_evidence]
per_item = 4.0
maximum = 8.0

[scores.maintainability]
maximum = 20.0
ci_workflow = 10.0

[scores.maintainability.directory_count]
"1" = 4.0
"2" = 7.0
"3" = 10.0

[scores.research_context]
maximum = 50.0
paper_link = 35.0

[scores.research_context.academic_keyword]
per_item = 1.5
maximum = 15.0

[scores.trust_multiplier]
academic_domain = 1.5
verified_organization = 1.3
account_age_years = 3
experienced_account = 1.1
default = 1.0
```

## 3. 評価規則

| 提供形態                 | 初期点 | 意図                                               |
| :----------------------- | -----: | :------------------------------------------------- |
| `library`                |     12 | 他プログラムから直接利用できる提供物を最優先する。 |
| `modular_application`    |      8 | 実行入口を持つが、再利用可能なモジュールを備える。 |
| `executable_application` |      2 | 除外せず、再利用性の不確実さを点差で表す。         |
| `unknown`                |      0 | 根拠不足のため加点しない。                         |

基礎スコアは `reusability + maintainability + research_context` とし、ハードフィルター通過時のみ信頼度乗数を適用する。各評価軸は設定された最大値で上限化し、総合スコアは小数第2位に丸める。科学計算・MLライブラリおよびPapers with Codeは検索・表示属性であり、直接加点しない。

## 4. 再現性と移行

観測レポートには、適用したプロファイルID、プロファイル版、設定ファイルのSHA-256、掲載閾値、評価軸別内訳を記録する。設定を変更する際は、同一入力で前後の掲載件数と提供形態別・シードカテゴリ別の通過率を比較する。`report_version: 3`はさらに、PWC照合状態、所有者種別・照会状態、組織認証・学術ドメイン、アカウント年数帯、信頼度乗数、総合点分布、閾値通過率を集計する。比較方法とロールバック基準は[配点調整観測手順](../analysis/配点調整観測手順.md)に従う。PWC情報は最終公開アーカイブに由来する観測属性であり、直接加点には使用しない。

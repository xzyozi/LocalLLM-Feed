"""ScholarRepo-Finder パイプライン実行エントリーポイント。"""

from pathlib import Path

from scholarrepo_finder.builder import (
    build_phase1_observation_report,
    build_static_repo_items,
    generate_awesome_markdown,
    save_phase1_observation_report,
    save_static_json,
)
from scholarrepo_finder.collector import GitHubCollector, collect_seed_repositories, format_observer_summary
from scholarrepo_finder.extractor import extract_features
from scholarrepo_finder.models import ExtractedFeatures, RepoRaw, ScoreResult
from scholarrepo_finder.pwc import PapersWithCodeClient
from scholarrepo_finder.scorer import evaluate_repository
from scholarrepo_finder.scoring_config import DEFAULT_SCORING_CONFIG_PATH, load_scoring_config


def run_pipeline(
    collector: GitHubCollector | None = None,
    pwc_client: PapersWithCodeClient | None = None,
    public_data_dir: Path | str = "public/data",
    docs_dir: Path | str = "docs",
    config_path: Path | str = DEFAULT_SCORING_CONFIG_PATH,
    limit_per_query: int = 30,
) -> int:
    """設定検証、収集、評価、静的データ出力を順番に実行する。

    Args:
        collector: GitHubデータ収集用コレクター。未指定時は本番実装を生成する。
        pwc_client: PWCアーカイブ照合クライアント。未指定時は本番実装を生成する。
        public_data_dir: 配信用JSONと観測レポートの出力先。
        docs_dir: 自動生成Markdownの出力先。
        config_path: 検証するスコアリング設定TOMLへのパス。
        limit_per_query: シードクエリごとの収集上限。

    Returns:
        配信対象として出力したリポジトリ数。
    """
    from time import perf_counter

    pipeline_started_at = perf_counter()
    loaded_config = load_scoring_config(config_path)
    config = loaded_config.config
    owns_collector = collector is None
    owns_pwc_client = pwc_client is None
    col = collector or GitHubCollector()
    pwc = pwc_client or PapersWithCodeClient()

    print(f"⚙️  [Step 0/5] スコア設定 {config.profile.id} v{config.profile.version} を検証しました。")
    print("🚀 [Step 1/5] シードリポジトリの収集を開始...")
    step_started_at = perf_counter()
    try:
        raw_repos = collect_seed_repositories(col, limit_per_query=limit_per_query)
    finally:
        # run_pipeline内で生成したコレクターの接続だけを解放する。
        # 呼び出し元から渡されたコレクターは呼び出し元の責任で管理する。
        if owns_collector:
            col.close()
    step_elapsed_seconds = perf_counter() - step_started_at
    print(f"   -> {len(raw_repos)} 件のリポジトリメタデータを取得しました ({step_elapsed_seconds:.1f} 秒)")
    print(format_observer_summary(col.observer))

    print("🔬 [Step 2/5] 特徴抽出とスコアリングを実行中...")
    step_started_at = perf_counter()
    evaluated_records: list[tuple[RepoRaw, ScoreResult, ExtractedFeatures]] = []
    total_repositories = len(raw_repos)
    try:
        for index, raw in enumerate(raw_repos, start=1):
            raw.pwc_match = pwc.lookup_repository(raw.html_url)
            features = extract_features(raw)
            evaluated_records.append((raw, evaluate_repository(raw, features, loaded_config), features))
            if index % 100 == 0 or index == total_repositories:
                elapsed_seconds = perf_counter() - step_started_at
                print(f"   -> Step 2: {index}/{total_repositories} 件を評価済み ({elapsed_seconds:.1f} 秒経過)")
    finally:
        # run_pipeline内で生成したPWCクライアントの接続だけを解放する。
        # 呼び出し元から渡されたクライアントは呼び出し元の責任で管理する。
        if owns_pwc_client:
            pwc.close()
    step_elapsed_seconds = perf_counter() - step_started_at
    print(f"   -> Step 2 完了: {total_repositories} 件を評価 ({step_elapsed_seconds:.1f} 秒)")

    print("📊 [Step 3/5] 提供形態・シードカテゴリの観測レポートを作成中...")
    step_started_at = perf_counter()
    observation_report = build_phase1_observation_report(evaluated_records, loaded_config)
    step_elapsed_seconds = perf_counter() - step_started_at
    print(f"   -> Step 3 完了 ({step_elapsed_seconds:.1f} 秒)")

    print("📦 [Step 4/5] 配信データの軽量化とビルド...")
    step_started_at = perf_counter()
    static_items = build_static_repo_items(evaluated_records, config.indexing_threshold)
    step_elapsed_seconds = perf_counter() - step_started_at
    print(
        f"   -> 厳選基準 (Score >= {config.indexing_threshold}) をクリアした {len(static_items)} 件をインデックス化 "
        f"({step_elapsed_seconds:.1f} 秒)"
    )

    print("💾 [Step 5/5] 静的JSON、Markdown、観測レポートを出力...")
    step_started_at = perf_counter()
    public_path = Path(public_data_dir) / "repos.json"
    docs_path = Path(docs_dir)
    save_static_json(static_items, public_path)
    generate_awesome_markdown(
        static_items,
        docs_path / "awesome_scholar_repos.md",
        config.indexing_threshold,
        config.profile.id,
    )
    save_phase1_observation_report(observation_report, Path(public_data_dir) / "function_provider_observations.json")
    step_elapsed_seconds = perf_counter() - step_started_at
    print(f"   -> JSON: {public_path}")
    print(f"   -> MD:   {docs_path / 'awesome_scholar_repos.md'}")
    print(f"   -> Analysis: {Path(public_data_dir) / 'function_provider_observations.json'}")
    print(f"   -> Step 5 完了 ({step_elapsed_seconds:.1f} 秒)")
    print(f"✨ パイプラインが正常終了しました！ 合計 {perf_counter() - pipeline_started_at:.1f} 秒")
    return len(static_items)


if __name__ == "__main__":
    run_pipeline()

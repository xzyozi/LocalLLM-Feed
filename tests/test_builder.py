"""静的データビルダーおよびパイプラインのテスト。"""

from datetime import datetime, timezone
import json
from pathlib import Path
from unittest.mock import MagicMock

from scholarrepo_finder.builder import (
    build_phase1_observation_report,
    build_static_repo_items,
    generate_awesome_markdown,
    save_static_json,
)
from scholarrepo_finder.models import (
    ExtractedFeatures,
    GitHubOwnerProfile,
    PapersWithCodeMatch,
    RepoRaw,
    ScoreResult,
)
from scholarrepo_finder.pipeline import run_pipeline
from scholarrepo_finder.scoring_config import load_scoring_config

MINIMUM_SCORE = 60.0


def create_raw(repo_id: str, now: datetime, language: str = "Python") -> RepoRaw:
    """ビルダーテスト用の生リポジトリを生成する。"""
    owner, name = repo_id.split("/", 1)
    return RepoRaw(
        repo_id=repo_id,
        name=name,
        owner=owner,
        description=f"{name} description",
        html_url=f"https://github.com/{repo_id}",
        created_at=now,
        last_commit_at=now,
        primary_language=language,
    )


def test_build_static_repo_items() -> None:
    """設定済み閾値で配信項目をフィルタリングし、内訳を保持することを検証する。"""
    now = datetime.now(timezone.utc)
    raw1 = create_raw("lab/repo1", now)
    raw2 = create_raw("lab/repo2", now, "Rust")
    raw2.pwc_match = PapersWithCodeMatch(
        lookup_status="matched_official",
        is_official=True,
        repository_url=raw2.html_url,
        paper_url="https://arxiv.org/abs/2401.00001",
    )
    raw3 = create_raw("lab/repo3", now)
    records = [
        (
            raw1,
            ScoreResult(repo_id=raw1.repo_id, hard_filter_passed=True, total_score=85.0, reusability_score=20.0),
            ExtractedFeatures(repo_id=raw1.repo_id, has_doi_link=True, delivery_form="library"),
        ),
        (
            raw2,
            ScoreResult(repo_id=raw2.repo_id, hard_filter_passed=True, total_score=95.0, maintainability_score=20.0),
            ExtractedFeatures(repo_id=raw2.repo_id, delivery_form="modular_application"),
        ),
        (
            raw3,
            ScoreResult(repo_id=raw3.repo_id, hard_filter_passed=True, total_score=40.0),
            ExtractedFeatures(repo_id=raw3.repo_id),
        ),
    ]

    items = build_static_repo_items(records, MINIMUM_SCORE)

    assert [item.id for item in items] == ["lab/repo2", "lab/repo1"]
    assert items[1].paper is True
    assert items[0].pwc_status == "matched_official"
    assert items[0].pwc_paper_url == "https://arxiv.org/abs/2401.00001"
    assert items[1].delivery_form == "library"
    assert items[1].score_breakdown["reusability"] == 20.0


def test_save_static_json(tmp_path: Path) -> None:
    """配信JSONが設定駆動の追加フィールドを含むことを検証する。"""
    now = datetime.now(timezone.utc)
    raw = create_raw("lab/r", now)
    records = [
        (
            raw,
            ScoreResult(repo_id=raw.repo_id, hard_filter_passed=True, total_score=75.0),
            ExtractedFeatures(repo_id=raw.repo_id),
        )
    ]
    items = build_static_repo_items(records, MINIMUM_SCORE)
    output_path = tmp_path / "data" / "repos.json"
    save_static_json(items, output_path)

    content = json.loads(output_path.read_text(encoding="utf-8"))
    assert content[0]["id"] == "lab/r"
    assert content[0]["score"] == 75.0
    assert content[0]["score_breakdown"] == {
        "reusability": 0.0,
        "maintainability": 0.0,
        "research_context": 0.0,
    }


def test_generate_awesome_markdown(tmp_path: Path) -> None:
    """生成Markdownがプロファイルと可変掲載閾値を表示することを検証する。"""
    now = datetime.now(timezone.utc)
    raw = create_raw("lab/r", now)
    records = [
        (
            raw,
            ScoreResult(repo_id=raw.repo_id, hard_filter_passed=True, total_score=88.0),
            ExtractedFeatures(repo_id=raw.repo_id),
        )
    ]
    items = build_static_repo_items(records, MINIMUM_SCORE)
    output_path = tmp_path / "awesome_scholar_repos.md"
    generate_awesome_markdown(items, output_path, MINIMUM_SCORE, "reusability-v1")

    markdown = output_path.read_text(encoding="utf-8")
    assert "Awesome Scholar Repositories" in markdown
    assert "[lab/r](https://github.com/lab/r)" in markdown
    assert "reusability-v1" in markdown
    assert "60.0" in markdown



def test_run_pipeline(tmp_path: Path) -> None:
    """パイプラインが設定を読み込み、新スコアで全成果物を出力することを検証する。"""
    now = datetime.now(timezone.utc)
    raw = RepoRaw(
        repo_id="mock/scholar-sim",
        name="scholar-sim",
        owner="mock",
        description="A benchmark simulation framework.",
        html_url="https://github.com/mock/scholar-sim",
        license_spdx="MIT",
        created_at=now,
        last_commit_at=now,
        primary_language="Python",
        readme_raw="Usage examples explain configuration for a benchmark simulation with experimental results. Paper: https://doi.org/10.1016/j.sim.2024.01",
        file_tree=[
            "src/sim/__init__.py",
            "src/sim/engine.py",
            "src/sim.py",
            "tests/test_sim.py",
            "docs/index.md",
            "config/settings.json",
            ".github/workflows/ci.yml",
        ],
    )
    mock_collector = MagicMock()
    mock_collector.search_repositories.return_value = [{"full_name": "mock/scholar-sim"}]
    mock_collector.fetch_repository_details.return_value = raw
    mock_pwc_client = MagicMock()
    mock_pwc_client.lookup_repository.return_value = PapersWithCodeMatch(
        lookup_status="matched_official",
        is_official=True,
        repository_url=raw.html_url,
    )

    public_dir = tmp_path / "public" / "data"
    docs_dir = tmp_path / "docs"
    count = run_pipeline(
        collector=mock_collector,
        pwc_client=mock_pwc_client,
        public_data_dir=public_dir,
        docs_dir=docs_dir,
        limit_per_query=1,
    )

    assert count == 1
    repos = json.loads((public_dir / "repos.json").read_text(encoding="utf-8"))
    report = json.loads((public_dir / "function_provider_observations.json").read_text(encoding="utf-8"))
    assert repos[0]["delivery_form"] == "library"
    assert raw.pwc_match is not None
    assert raw.pwc_match.lookup_status == "matched_official"
    mock_pwc_client.lookup_repository.assert_called_once_with(raw.html_url)
    assert report["profile"]["id"] == "reusability-v1"
    assert (docs_dir / "awesome_scholar_repos.md").exists()


def test_build_phase1_observation_report_includes_enrichment_metrics() -> None:
    """観測レポートがPWC照合と所有者信頼度の分布を記録する。"""
    now = datetime.now(timezone.utc)
    raw = create_raw("lab/verified-tool", now)
    raw.seed_categories = ["simulation"]
    raw.owner_profile = GitHubOwnerProfile(
        login="lab",
        account_type="Organization",
        email_domain="lab.edu",
        is_verified_org=True,
        account_age_years=8,
        lookup_status="found",
    )
    raw.pwc_match = PapersWithCodeMatch(
        lookup_status="matched_official",
        is_official=True,
        repository_url=raw.html_url,
    )
    score = ScoreResult(
        repo_id=raw.repo_id,
        hard_filter_passed=True,
        reusability_score=20.0,
        maintainability_score=15.0,
        research_context_score=20.0,
        base_repo_score=55.0,
        user_trust_multiplier=1.3,
        total_score=71.5,
    )
    features = ExtractedFeatures(
        repo_id=raw.repo_id,
        delivery_form="library",
        is_pwc_official=True,
        is_verified_org=True,
        is_edu_or_ac_domain=True,
        author_account_age_years=8,
    )

    report = build_phase1_observation_report([(raw, score, features)], load_scoring_config())

    assert report["report_version"] == 3
    assert report["summary"]["pwc_lookup_status_counts"] == {"matched_official": 1}
    assert report["summary"]["owner_account_type_counts"] == {"Organization": 1}
    assert report["summary"]["verified_organization_count"] == 1
    assert report["summary"]["account_age_year_buckets"] == {"6_or_more": 1}
    assert report["evaluations"][0]["user_trust_multiplier"] == 1.3

"""データモデルの単体テスト."""

from datetime import datetime
from scholarrepo_finder.models import ExtractedFeatures, RepoRaw, ScoreResult, StaticRepoItem


def test_repo_raw_model() -> None:
    """RepoRaw モデルのインスタンス化とプロパティ検証."""
    now = datetime.now()
    raw = RepoRaw(
        repo_id="test/repo",
        name="repo",
        owner="test",
        description="A test repo",
        html_url="https://github.com/test/repo",
        stars=10,
        forks=2,
        created_at=now,
        last_commit_at=now,
        license_spdx="MIT",
        primary_language="Python",
        topics=["simulation", "optimization"],
    )
    assert raw.repo_id == "test/repo"
    assert raw.stars == 10
    assert raw.default_branch == "main"
    assert raw.license_spdx == "MIT"


def test_extracted_features_model() -> None:
    """ExtractedFeatures モデルのデフォルト値および設定検証."""
    features = ExtractedFeatures(
        repo_id="test/repo",
        has_src_or_app_dir=True,
        has_tests_dir=True,
        has_ci_workflow=True,
        scientific_libs_detected=["numpy", "scipy"],
        has_doi_link=True,
        is_edu_or_ac_domain=True,
    )
    assert features.has_src_or_app_dir is True
    assert "numpy" in features.scientific_libs_detected
    assert features.has_doi_link is True
    assert features.is_edu_or_ac_domain is True
    assert features.author_account_age_years == 0


def test_score_result_model() -> None:
    """ScoreResult モデルのスコア計算値保持検証."""
    score = ScoreResult(
        repo_id="test/repo",
        hard_filter_passed=True,
        reusability_score=30.0,
        maintainability_score=20.0,
        research_context_score=35.0,
        base_repo_score=85.0,
        user_trust_multiplier=1.3,
        total_score=110.5,
        profile_id="reusability-v1",
        profile_version=1,
        config_sha256="a" * 64,
        indexing_threshold=60.0,
    )
    assert score.hard_filter_passed is True
    assert score.reusability_score == 30.0
    assert score.total_score == 110.5
    assert score.reject_reason is None


def test_static_repo_item_model() -> None:
    """StaticRepoItem 配信用軽量モデルの検証."""
    item = StaticRepoItem(
        id="test/repo",
        name="repo",
        desc="A test repo",
        lang="Python",
        topics=["simulation"],
        stars=10,
        updated="2026-08-31",
        score=85.5,
        paper=True,
        edu=True,
        libs=["numpy"],
        url="https://github.com/test/repo",
    )
    assert item.id == "test/repo"
    assert item.score == 85.5
    assert item.paper is True
    # JSONシリアライズ確認
    json_data = item.model_dump_json()
    assert '"score":85.5' in json_data

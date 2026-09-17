"""設定駆動スコアリングModuleのテスト。"""

from datetime import datetime, timedelta, timezone

from scholarrepo_finder.models import ExtractedFeatures, RepoRaw
from scholarrepo_finder.scorer import (
    calculate_maintainability_score,
    calculate_research_context_score,
    calculate_reusability_score,
    calculate_user_trust_multiplier,
    check_hard_filters,
    evaluate_repository,
)
from scholarrepo_finder.scoring_config import load_scoring_config

LOADED_CONFIG = load_scoring_config()
CONFIG = LOADED_CONFIG.config


def create_sample_raw(
    license_spdx: str | None = "MIT",
    days_ago: int = 30,
    readme: str = "This is a sufficiently long README text containing detailed descriptions, benchmarks, algorithm formulations, and usage guides for simulation experiments.",
) -> RepoRaw:
    """テスト用のRepoRawを生成する。"""
    now = datetime.now(timezone.utc)
    return RepoRaw(
        repo_id="test/repo",
        name="repo",
        owner="test",
        description="A test repo",
        html_url="https://github.com/test/repo",
        stars=10,
        forks=2,
        created_at=now - timedelta(days=365),
        last_commit_at=now - timedelta(days=days_ago),
        license_spdx=license_spdx,
        primary_language="Python",
        readme_raw=readme,
    )


def test_check_hard_filters_pass() -> None:
    """正常リポジトリが設定済みハードフィルターを通過することを検証する。"""
    passed, reason = check_hard_filters(create_sample_raw(), CONFIG)
    assert passed is True
    assert reason is None


def test_check_hard_filters_rejections() -> None:
    """ライセンス、陳腐化、READMEの除外規則を検証する。"""
    assert check_hard_filters(create_sample_raw(license_spdx=None), CONFIG)[0] is False
    assert check_hard_filters(create_sample_raw(days_ago=365 * 6), CONFIG)[0] is False
    assert check_hard_filters(create_sample_raw(readme="Short"), CONFIG)[0] is False


def test_calculate_reusability_score() -> None:
    """再利用性根拠が設定上限まで加点されることを検証する。"""
    features = ExtractedFeatures(
        repo_id="test/repo",
        delivery_form="library",
        public_api_evidence=["package", "export"],
        module_partition_evidence=["modules", "headers"],
        usage_evidence=["installation", "usage", "examples"],
        configurable_io_evidence=["config", "cli"],
    )
    assert calculate_reusability_score(features, CONFIG) == 30.0


def test_calculate_maintainability_score() -> None:
    """ディレクトリ構成とCIから保守性を算出することを検証する。"""
    features = ExtractedFeatures(
        repo_id="test/repo",
        has_src_or_app_dir=True,
        has_tests_dir=True,
        has_docs_dir=True,
        has_ci_workflow=True,
    )
    assert calculate_maintainability_score(features, CONFIG) == 20.0


def test_calculate_research_context_score() -> None:
    """論文リンクとキーワード根拠から研究文脈を算出することを検証する。"""
    features = ExtractedFeatures(
        repo_id="test/repo",
        has_arxiv_link=True,
        academic_keyword_evidence=["benchmark"] * 10,
        is_pwc_official=True,
    )
    assert calculate_research_context_score(features, CONFIG) == 50.0



def test_calculate_user_trust_multiplier() -> None:
    """設定に基づいて著者信頼度乗数を選ぶことを検証する。"""
    assert calculate_user_trust_multiplier(ExtractedFeatures(repo_id="t/r", is_edu_or_ac_domain=True), CONFIG) == 1.5
    assert calculate_user_trust_multiplier(ExtractedFeatures(repo_id="t/r", is_verified_org=True), CONFIG) == 1.3
    assert calculate_user_trust_multiplier(ExtractedFeatures(repo_id="t/r", author_account_age_years=4), CONFIG) == 1.1
    assert calculate_user_trust_multiplier(ExtractedFeatures(repo_id="t/r"), CONFIG) == 1.0


def test_evaluate_repository_comprehensive() -> None:
    """評価結果に新しい内訳と設定識別子が記録されることを検証する。"""
    features = ExtractedFeatures(
        repo_id="test/repo",
        has_src_or_app_dir=True,
        has_tests_dir=True,
        has_ci_workflow=True,
        delivery_form="library",
        public_api_evidence=["package", "export"],
        module_partition_evidence=["modules", "headers"],
        usage_evidence=["usage", "examples", "installation"],
        configurable_io_evidence=["config", "cli"],
        has_arxiv_link=True,
        academic_keyword_evidence=["benchmark"] * 4,
        is_edu_or_ac_domain=True,
    )

    result = evaluate_repository(create_sample_raw(), features, LOADED_CONFIG)

    assert result.hard_filter_passed is True
    assert result.reusability_score == 30.0
    assert result.maintainability_score == 17.0
    assert result.research_context_score == 41.0
    assert result.base_repo_score == 88.0
    assert result.user_trust_multiplier == 1.5
    assert result.total_score == 132.0
    assert result.profile_id == "reusability-v1"
    assert result.profile_version == 1
    assert result.config_sha256 == LOADED_CONFIG.sha256

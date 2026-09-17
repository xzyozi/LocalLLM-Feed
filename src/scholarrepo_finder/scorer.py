"""設定駆動のリポジトリ評価・ハードフィルタリングModule。"""

from datetime import datetime, timezone

from scholarrepo_finder.models import ExtractedFeatures, RepoRaw, ScoreResult
from scholarrepo_finder.scoring_config import LoadedScoringConfig, ScoringConfig


def check_hard_filters(
    raw: RepoRaw,
    config: ScoringConfig,
    now: datetime | None = None,
) -> tuple[bool, str | None]:
    """リポジトリが設定されたハードフィルターを満たすか判定する。

    Args:
        raw: 評価対象のリポジトリ情報。
        config: 検証済みスコアリング設定。
        now: 評価基準日時。未指定時は現在のUTC時刻。

    Returns:
        合格フラグと、不合格時の理由。
    """
    if not raw.license_spdx or not raw.license_spdx.strip():
        return False, "OSSライセンスが明記されていないか不正です。"

    current_time = now or datetime.now(timezone.utc)
    commit_time = raw.last_commit_at
    if commit_time.tzinfo is None:
        commit_time = commit_time.replace(tzinfo=timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    inactive_years = config.hard_filters.max_inactive_years
    days_since_last_commit = (current_time - commit_time).days
    if days_since_last_commit > inactive_years * 365:
        return False, f"最終コミットから{inactive_years}年以上が経過しています ({days_since_last_commit // 365}年前)。"

    minimum_readme_length = config.hard_filters.min_readme_char_length
    readme_length = len((raw.readme_raw or "").strip())
    if readme_length < minimum_readme_length:
        return False, f"READMEの文字数が極小（{readme_length}文字）のため情報が不足しています。"

    return True, None


def _capped_evidence_score(evidence: list[str], per_item: float, maximum: float) -> float:
    """根拠件数に応じた加点を上限付きで算出する。"""
    return min(len(evidence) * per_item, maximum)


def calculate_reusability_score(features: ExtractedFeatures, config: ScoringConfig) -> float:
    """提供形態と再利用性根拠から再利用性スコアを算出する。"""
    weights = config.scores.reusability
    score = weights.delivery_form.get(features.delivery_form, 0.0)
    score += _capped_evidence_score(
        features.public_api_evidence,
        weights.public_api_evidence.per_item,
        weights.public_api_evidence.maximum,
    )
    score += _capped_evidence_score(
        features.module_partition_evidence,
        weights.module_partition_evidence.per_item,
        weights.module_partition_evidence.maximum,
    )
    score += _capped_evidence_score(
        features.usage_evidence,
        weights.usage_evidence.per_item,
        weights.usage_evidence.maximum,
    )
    score += _capped_evidence_score(
        features.configurable_io_evidence,
        weights.configurable_io_evidence.per_item,
        weights.configurable_io_evidence.maximum,
    )
    return min(score, weights.maximum)


def calculate_maintainability_score(features: ExtractedFeatures, config: ScoringConfig) -> float:
    """構成分離とCIから保守性スコアを算出する。"""
    weights = config.scores.maintainability
    directory_count = sum((features.has_src_or_app_dir, features.has_tests_dir, features.has_docs_dir))
    score = weights.directory_count.get(directory_count, 0.0)
    if features.has_ci_workflow:
        score += weights.ci_workflow
    return min(score, weights.maximum)


def calculate_research_context_score(features: ExtractedFeatures, config: ScoringConfig) -> float:
    """論文リンクと学術キーワード根拠から研究文脈スコアを算出する。"""
    weights = config.scores.research_context
    score = weights.paper_link if features.has_doi_link or features.has_arxiv_link else 0.0
    score += _capped_evidence_score(
        features.academic_keyword_evidence,
        weights.academic_keyword.per_item,
        weights.academic_keyword.maximum,
    )
    return min(score, weights.maximum)


def calculate_user_trust_multiplier(features: ExtractedFeatures, config: ScoringConfig) -> float:
    """著者情報から設定された信頼度乗数を選択する。"""
    weights = config.scores.trust_multiplier
    if features.is_edu_or_ac_domain:
        return weights.academic_domain
    if features.is_verified_org:
        return weights.verified_organization
    if features.author_account_age_years >= weights.account_age_years:
        return weights.experienced_account
    return weights.default


def evaluate_repository(
    raw: RepoRaw,
    features: ExtractedFeatures,
    loaded_config: LoadedScoringConfig,
    now: datetime | None = None,
) -> ScoreResult:
    """検証済み設定を用いてリポジトリを評価する。

    Args:
        raw: 評価対象のリポジトリ情報。
        features: 抽出済み特徴量。
        loaded_config: 検証済み設定と設定ハッシュ。
        now: 評価基準日時。未指定時は現在日時。

    Returns:
        評価軸別内訳と設定識別子を含む評価結果。
    """
    config = loaded_config.config
    passed, reject_reason = check_hard_filters(raw, config, now)
    reusability_score = calculate_reusability_score(features, config)
    maintainability_score = calculate_maintainability_score(features, config)
    research_context_score = calculate_research_context_score(features, config)
    base_repo_score = reusability_score + maintainability_score + research_context_score
    user_multiplier = calculate_user_trust_multiplier(features, config)
    total_score = round(base_repo_score * user_multiplier, 2) if passed else 0.0

    return ScoreResult(
        repo_id=raw.repo_id,
        hard_filter_passed=passed,
        reject_reason=reject_reason,
        reusability_score=reusability_score,
        maintainability_score=maintainability_score,
        research_context_score=research_context_score,
        base_repo_score=base_repo_score,
        user_trust_multiplier=user_multiplier,
        total_score=total_score,
        profile_id=config.profile.id,
        profile_version=config.profile.version,
        config_sha256=loaded_config.sha256,
        indexing_threshold=config.indexing_threshold,
        evaluated_at=now or datetime.now(),
    )

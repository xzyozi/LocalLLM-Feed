"""ScholarRepo-Finder データモデルおよび DTO 定義モジュール。"""

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class GitHubOwnerProfile(BaseModel):
    """GitHub所有者・組織から安全に正規化した信頼度評価用属性。"""

    login: str = Field(..., min_length=1, description="所有者アカウント名")
    account_type: str = Field("Unknown", description="GitHubの所有者種別")
    email_domain: Optional[str] = Field(None, description="公開メールから抽出したドメインのみ")
    is_verified_org: bool = Field(False, description="認証済み組織フラグ")
    account_age_years: int = Field(0, ge=0, description="アカウント経過年数")
    lookup_status: Literal["not_checked", "found", "not_found", "failed", "skipped_rate_limited"] = Field(
        "not_checked", description="所有者プロフィール照会の結果"
    )


class PapersWithCodeMatch(BaseModel):
    """Papers with Codeアーカイブにおけるリポジトリ照合結果。"""

    lookup_status: Literal["not_checked", "matched_official", "matched_unofficial", "not_found", "failed"] = Field(
        "not_checked", description="PWCアーカイブ照合状態"
    )
    is_official: bool = Field(False, description="公式実装として登録されているか")
    repository_url: Optional[str] = Field(None, description="照合に使ったGitHubリポジトリURL")
    paper_url: Optional[str] = Field(None, description="関連論文の公開URL")
    arxiv_id: Optional[str] = Field(None, description="関連論文のarXiv識別子")
    source: str = Field("pwc_archive", description="照合データの取得元")


class RepoRaw(BaseModel):
    """データ収集層で取得されるリポジトリの生メタデータ。"""

    repo_id: str = Field(..., description="リポジトリ識別子 (owner/repo)")
    name: str = Field(..., description="リポジトリ名")
    owner: str = Field(..., description="所有者アカウント名")
    owner_profile: Optional[GitHubOwnerProfile] = Field(None, description="所有者・組織エンリッチメント結果")
    pwc_match: Optional[PapersWithCodeMatch] = Field(None, description="Papers with Codeアーカイブ照合結果")
    description: Optional[str] = Field(None, description="リポジトリ概要説明文")
    html_url: str = Field(..., description="GitHub リポジトリ URL")
    default_branch: str = Field("main", description="デフォルトブランチ名")
    stars: int = Field(0, ge=0, description="スター数")
    forks: int = Field(0, ge=0, description="フォーク数")
    created_at: datetime = Field(..., description="作成日時")
    last_commit_at: datetime = Field(..., description="最終コミット日時")
    license_spdx: Optional[str] = Field(None, description="SPDX ライセンス識別子")
    primary_language: Optional[str] = Field(None, description="主要プログラミング言語")
    topics: List[str] = Field(default_factory=list, description="トピックタグ一覧")
    seed_categories: List[str] = Field(default_factory=list, description="収集シードから判定した分野カテゴリ一覧")
    readme_raw: Optional[str] = Field(None, description="README 生テキスト")
    file_tree: List[str] = Field(default_factory=list, description="リポジトリ内ファイルパス一覧")
    dependency_files: Dict[str, str] = Field(default_factory=dict, description="依存定義ファイル名と内容")
    etag: Optional[str] = Field(None, description="条件付きリクエスト用 ETag")


class ExtractedFeatures(BaseModel):
    """特徴抽出層で生成される特徴量ベクトル。"""

    repo_id: str = Field(..., description="リポジトリ識別子 (owner/repo)")
    has_src_or_app_dir: bool = Field(False, description="src/ または app/ ディレクトリ存在フラグ")
    has_tests_dir: bool = Field(False, description="tests/ または test/ ディレクトリ存在フラグ")
    has_docs_dir: bool = Field(False, description="docs/ または doc/ ディレクトリ存在フラグ")
    has_ci_workflow: bool = Field(False, description="CI 設定ファイル存在フラグ")
    scientific_libs_detected: List[str] = Field(default_factory=list, description="検索・表示用の科学系ライブラリ")
    delivery_form: str = Field("unknown", description="提供形態")
    public_api_evidence: List[str] = Field(default_factory=list, description="公開API・ライブラリ提供の根拠")
    module_partition_evidence: List[str] = Field(default_factory=list, description="責務別モジュール分割の根拠")
    usage_evidence: List[str] = Field(default_factory=list, description="利用方法の根拠")
    configurable_io_evidence: List[str] = Field(default_factory=list, description="設定可能な入出力の根拠")
    has_doi_link: bool = Field(False, description="DOI リンク検出フラグ")
    has_arxiv_link: bool = Field(False, description="arXiv リンク検出フラグ")
    is_pwc_official: bool = Field(False, description="検索・表示用のPapers with Code登録フラグ")
    academic_keyword_evidence: List[str] = Field(default_factory=list, description="学術キーワードの一致根拠")
    academic_keyword_score: float = Field(0.0, ge=0.0, description="互換用の学術キーワード一致件数")
    author_email_domain: Optional[str] = Field(None, description="リポジトリ所有者のメールドメイン")
    is_edu_or_ac_domain: bool = Field(False, description="教育・研究機関ドメインフラグ")
    is_verified_org: bool = Field(False, description="GitHub 認証済み組織フラグ")
    author_account_age_years: int = Field(0, ge=0, description="所有者アカウント経過年数")


class ScoreResult(BaseModel):
    """設定駆動の評価・選別結果。"""

    repo_id: str = Field(..., description="リポジトリ識別子 (owner/repo)")
    hard_filter_passed: bool = Field(False, description="ハードフィルター合否")
    reject_reason: Optional[str] = Field(None, description="不合格時の除外理由")
    reusability_score: float = Field(0.0, ge=0.0, description="再利用性スコア")
    maintainability_score: float = Field(0.0, ge=0.0, description="保守性スコア")
    research_context_score: float = Field(0.0, ge=0.0, description="研究文脈スコア")
    base_repo_score: float = Field(0.0, ge=0.0, description="評価軸合計")
    user_trust_multiplier: float = Field(1.0, gt=0.0, description="著者信頼度乗数")
    total_score: float = Field(0.0, ge=0.0, description="最終総合スコア")
    profile_id: str = Field("unconfigured", description="適用したスコアプロファイルID")
    profile_version: int = Field(0, ge=0, description="適用したスコアプロファイル版")
    config_sha256: str = Field("", description="適用した設定ファイルのSHA-256")
    indexing_threshold: float = Field(0.0, ge=0.0, description="適用した掲載閾値")
    evaluated_at: datetime = Field(default_factory=datetime.now, description="評価日時")


class StaticRepoItem(BaseModel):
    """GitHub Pages 配信用の軽量リポジトリモデル。"""

    id: str = Field(..., description="リポジトリ識別子 (owner/repo)")
    name: str = Field(..., description="リポジトリ名")
    desc: str = Field("", description="概要文 (最大 200 文字)")
    lang: str = Field("Unknown", description="主要プログラミング言語")
    topics: List[str] = Field(default_factory=list, description="トピック一覧")
    stars: int = Field(0, ge=0, description="スター数")
    updated: str = Field(..., description="最終コミット日 (YYYY-MM-DD)")
    score: float = Field(..., ge=0.0, description="総合スコア")
    score_breakdown: Dict[str, float] = Field(default_factory=dict, description="評価軸別スコア")
    delivery_form: str = Field("unknown", description="提供形態")
    reusability_evidence: List[str] = Field(default_factory=list, description="再利用性根拠")
    paper: bool = Field(False, description="論文リンク有無フラグ")
    pwc_status: str = Field("not_checked", description="Papers with Codeアーカイブ照合状態")
    pwc_paper_url: Optional[str] = Field(None, description="PWCアーカイブが示す関連論文URL")
    edu: bool = Field(False, description="アカデミック著者フラグ")
    libs: List[str] = Field(default_factory=list, description="検索・表示用の科学計算ライブラリ")
    url: str = Field(..., description="リポジトリ URL")

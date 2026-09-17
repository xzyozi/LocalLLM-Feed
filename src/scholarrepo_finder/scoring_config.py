"""設定駆動スコアリング用の設定読込・検証Module。"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import tomllib

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

DEFAULT_SCORING_CONFIG_PATH = Path("config/scoring.toml")
_DELIVERY_FORMS = {"library", "modular_application", "executable_application", "unknown"}
_DIRECTORY_COUNTS = {1, 2, 3}


class ScoringConfigError(ValueError):
    """スコアリング設定が仕様を満たさない場合に送出する例外。"""


class _StrictConfigModel(BaseModel):
    """未知キーを許可しない設定モデルの共通基底。"""

    model_config = ConfigDict(extra="forbid")


class ProfileConfig(_StrictConfigModel):
    """スコアプロファイルの識別情報。"""

    id: str = Field(min_length=1)
    version: int = Field(ge=1)


class HardFilterConfig(_StrictConfigModel):
    """候補除外に使用する設定。"""

    max_inactive_years: int = Field(ge=0)
    min_readme_char_length: int = Field(ge=0)


class EvidenceWeightConfig(_StrictConfigModel):
    """根拠件数に応じて加点する評価規則。"""

    per_item: float = Field(ge=0.0)
    maximum: float = Field(ge=0.0)


class ReusabilityScoreConfig(_StrictConfigModel):
    """再利用性評価の配点設定。"""

    maximum: float = Field(gt=0.0)
    delivery_form: dict[str, float]
    public_api_evidence: EvidenceWeightConfig
    module_partition_evidence: EvidenceWeightConfig
    usage_evidence: EvidenceWeightConfig
    configurable_io_evidence: EvidenceWeightConfig

    @model_validator(mode="after")
    def validate_weights(self) -> "ReusabilityScoreConfig":
        """提供形態と評価軸の上限を検証する。"""
        if set(self.delivery_form) != _DELIVERY_FORMS:
            raise ValueError("delivery_form は4つの提供形態をすべて定義する必要があります。")
        if any(value < 0.0 for value in self.delivery_form.values()):
            raise ValueError("delivery_form の配点は0以上である必要があります。")

        possible_maximum = max(self.delivery_form.values()) + sum(
            (
                self.public_api_evidence.maximum,
                self.module_partition_evidence.maximum,
                self.usage_evidence.maximum,
                self.configurable_io_evidence.maximum,
            )
        )
        if possible_maximum > self.maximum:
            raise ValueError("再利用性の個別配点上限が評価軸のmaximumを超えています。")
        return self


class MaintainabilityScoreConfig(_StrictConfigModel):
    """保守性評価の配点設定。"""

    maximum: float = Field(gt=0.0)
    directory_count: dict[int, float]
    ci_workflow: float = Field(ge=0.0)

    @model_validator(mode="after")
    def validate_weights(self) -> "MaintainabilityScoreConfig":
        """ディレクトリ分離度と評価軸の上限を検証する。"""
        if set(self.directory_count) != _DIRECTORY_COUNTS:
            raise ValueError("directory_count は1、2、3の配点をすべて定義する必要があります。")
        if any(value < 0.0 for value in self.directory_count.values()):
            raise ValueError("directory_count の配点は0以上である必要があります。")
        if max(self.directory_count.values()) + self.ci_workflow > self.maximum:
            raise ValueError("保守性の個別配点上限が評価軸のmaximumを超えています。")
        return self


class ResearchContextScoreConfig(_StrictConfigModel):
    """研究文脈評価の配点設定。"""

    maximum: float = Field(gt=0.0)
    paper_link: float = Field(ge=0.0)
    academic_keyword: EvidenceWeightConfig

    @model_validator(mode="after")
    def validate_weights(self) -> "ResearchContextScoreConfig":
        """研究文脈の個別配点が評価軸上限を超えないことを検証する。"""
        if self.paper_link + self.academic_keyword.maximum > self.maximum:
            raise ValueError("研究文脈の個別配点上限が評価軸のmaximumを超えています。")
        return self


class TrustMultiplierConfig(_StrictConfigModel):
    """著者信頼度乗数の設定。"""

    academic_domain: float = Field(gt=0.0)
    verified_organization: float = Field(gt=0.0)
    account_age_years: int = Field(ge=0)
    experienced_account: float = Field(gt=0.0)
    default: float = Field(gt=0.0)


class ScoresConfig(_StrictConfigModel):
    """全評価軸と信頼度乗数の設定。"""

    reusability: ReusabilityScoreConfig
    maintainability: MaintainabilityScoreConfig
    research_context: ResearchContextScoreConfig
    trust_multiplier: TrustMultiplierConfig


class ScoringConfig(_StrictConfigModel):
    """`config/scoring.toml` の検証済み設定。"""

    schema_version: int = Field(strict=True)
    profile: ProfileConfig
    hard_filters: HardFilterConfig
    indexing_threshold: float = Field(ge=0.0, strict=True)
    scores: ScoresConfig

    @model_validator(mode="after")
    def validate_schema_version(self) -> "ScoringConfig":
        """対応可能な設定スキーマ版だけを受け入れる。"""
        if self.schema_version != 1:
            raise ValueError("schema_version は1である必要があります。")
        return self


@dataclass(frozen=True)
class LoadedScoringConfig:
    """評価実行へ渡す検証済み設定と再現性情報。"""

    config: ScoringConfig
    sha256: str


def load_scoring_config(path: Path | str = DEFAULT_SCORING_CONFIG_PATH) -> LoadedScoringConfig:
    """TOML設定を読込み、検証済みの設定と内容ハッシュを返す。

    Args:
        path: スコアリング設定TOMLへのパス。

    Returns:
        検証済み設定と元ファイルのSHA-256を含むオブジェクト。

    Raises:
        ScoringConfigError: ファイル読み込み、TOML構文、または設定検証に失敗した場合。
    """
    config_path = Path(path)
    try:
        raw_bytes = config_path.read_bytes()
    except OSError as error:
        raise ScoringConfigError(f"スコアリング設定を読み込めません: {config_path}") from error

    try:
        raw_data = tomllib.loads(raw_bytes.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise ScoringConfigError(f"スコアリング設定はUTF-8のTOMLである必要があります: {config_path}") from error

    try:
        config = ScoringConfig.model_validate(raw_data)
    except ValidationError as error:
        raise ScoringConfigError(f"スコアリング設定が不正です: {error}") from error

    return LoadedScoringConfig(config=config, sha256=hashlib.sha256(raw_bytes).hexdigest())

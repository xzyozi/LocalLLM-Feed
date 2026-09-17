"""スコアリング設定ローダーの公開契約テスト。"""

import hashlib
from pathlib import Path

import pytest

from scholarrepo_finder.scoring_config import ScoringConfigError, load_scoring_config

DEFAULT_CONFIG_PATH = Path("config/scoring.toml")


def write_config(tmp_path: Path, content: str) -> Path:
    """一時設定を書き出して読込対象パスを返す。"""
    path = tmp_path / "scoring.toml"
    path.write_text(content, encoding="utf-8")
    return path


def default_config_text() -> str:
    """既定設定を異常系テストの基準値として読み込む。"""
    return DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")


def test_load_scoring_config_returns_content_sha256() -> None:
    """検証済み設定と入力バイト列のSHA-256を返す。"""
    raw_bytes = DEFAULT_CONFIG_PATH.read_bytes()
    loaded = load_scoring_config(DEFAULT_CONFIG_PATH)

    assert loaded.config.profile.id == "reusability-v1"
    assert loaded.sha256 == hashlib.sha256(raw_bytes).hexdigest()


@pytest.mark.parametrize(
    ("invalid_content", "reason"),
    [
        ("schema_version =", "TOML構文エラー"),
        (default_config_text().replace("indexing_threshold = 60.0", "unexpected = 1"), "必須キー欠落と未知キー"),
        (default_config_text().replace("schema_version = 1", "schema_version = true"), "真偽値の型不正"),
        (default_config_text().replace("indexing_threshold = 60.0", 'indexing_threshold = "60"'), "数値文字列の型不正"),
        (default_config_text().replace("paper_link = 35.0", "paper_link = -1.0"), "負の配点"),
        (default_config_text().replace("paper_link = 35.0", "paper_link = 45.0"), "評価軸上限超過"),
    ],
)
def test_load_scoring_config_rejects_invalid_input(
    tmp_path: Path, invalid_content: str, reason: str
) -> None:
    """構文、スキーマ、型、範囲、上限に反する設定を暗黙補正しない。"""
    with pytest.raises(ScoringConfigError):
        load_scoring_config(write_config(tmp_path, invalid_content))

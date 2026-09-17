"""初期プレースホルダーテスト."""

from scholarrepo_finder import __version__


def test_version() -> None:
    """パッケージバージョンの確認テスト."""
    assert __version__ == "0.1.0"

"""config ローダの単体テスト。"""

from __future__ import annotations

from pathlib import Path

from localllm_feed import config


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8", newline="\n")
    return p


def test_load_collection_config(tmp_path: Path) -> None:
    toml_text = (
        "schema_version = 1\n"
        "[collection]\n"
        "retention_days = 14\n"
        "max_records = 50\n"
        "min_downloads = 10\n"
        "gguf_only = true\n"
        "tldr_fetch_limit = 30\n"
        'authors = ["bartowski", "Qwen"]\n'
        "[popular_scan]\n"
        "enabled = false\n"
        "notify_min_downloads = 2000\n"
        "scan_limit = 20\n"
    )
    path = _write(tmp_path, "collection.toml", toml_text)
    cfg = config.load_collection_config(path)
    assert cfg.retention_days == 14
    assert cfg.tldr_fetch_limit == 30
    assert cfg.authors == ("bartowski", "Qwen")
    assert cfg.popular_scan.enabled is False
    assert cfg.popular_scan.notify_min_downloads == 2000


def test_load_collection_config_defaults(tmp_path: Path) -> None:
    path = _write(tmp_path, "collection.toml", "schema_version = 1\n")
    cfg = config.load_collection_config(path)
    assert cfg.retention_days == 30
    assert cfg.max_records == 300
    assert cfg.tldr_fetch_limit == 120
    assert cfg.authors == ()
    assert cfg.popular_scan.enabled is True


def test_load_scoring_config(tmp_path: Path) -> None:
    toml_text = 'schema_version = 1\n[profile]\nid = "x"\nversion = 1\n'
    path = _write(tmp_path, "scoring.toml", toml_text)
    data = config.load_scoring_config(path)
    assert data["profile"]["id"] == "x"

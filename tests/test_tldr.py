"""tldr モジュールの単体テスト。"""

from __future__ import annotations

from localllm_feed import tldr


def test_first_paragraph_after_heading() -> None:
    readme = "# My Model\n\nThis is a great **7B** model for chat.\n\n## Details\nmore text"
    result = tldr.extract_tldr(readme)
    assert "great 7B model for chat" in result
    assert "**" not in result


def test_paragraph_under_description_section() -> None:
    readme = "# Title\n\n## Description\n\nA compact reasoning model.\n\n## Usage\nrun it"
    result = tldr.extract_tldr(readme)
    assert "compact reasoning model" in result


def test_empty_readme_returns_empty() -> None:
    assert tldr.extract_tldr("") == ""
    assert tldr.extract_tldr("# Only Heading\n") == ""


def test_truncates_to_max_chars() -> None:
    body = "word " * 100
    readme = f"# T\n\n{body}"
    result = tldr.extract_tldr(readme, max_chars=50)
    assert len(result) <= 51
    assert result.endswith("…")


def test_strips_images_and_links() -> None:
    readme = "# T\n\n![badge](http://x/y.png) See [docs](http://d) here."
    result = tldr.extract_tldr(readme)
    assert "http" not in result
    assert "docs" in result
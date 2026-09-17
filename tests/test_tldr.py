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


def test_skips_boilerplate_and_uses_next_paragraph() -> None:
    readme = (
        "# Model-7B-GGUF\n\n"
        "static quants of https://huggingface.co/someone/Model-7B\n\n"
        "A powerful reasoning model tuned for coding tasks."
    )
    result = tldr.extract_tldr(readme)
    assert "static quants" not in result
    assert "reasoning model" in result


def test_bare_url_removed() -> None:
    readme = "# T\n\nSee https://example.com/page for details about this model."
    result = tldr.extract_tldr(readme)
    assert "http" not in result
    assert "details about this model" in result


def test_extract_base_model_id() -> None:
    readme = "# Q\n\nweighted/imatrix quants of https://huggingface.co/ManniX-ITA/Qwen3-27B\n"
    assert tldr.extract_base_model_id(readme) == "ManniX-ITA/Qwen3-27B"
    assert tldr.extract_base_model_id("# no link\n\ntext") == ""


def test_is_boilerplate_readme() -> None:
    assert tldr.is_boilerplate_readme("# M\n\nstatic quants of https://huggingface.co/a/b") is True
    assert tldr.is_boilerplate_readme("# M\n\nA great model.") is False

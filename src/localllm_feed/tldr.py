"""README からの TL;DR ルールベース抽出（LLF-DD-001 §2.4）。

生成AIは使用しない。以下を上から順に試し、最初に取得できたものを
1〜2文（最大 max_chars 文字）に整形して返す。取得不能なら空文字。

1. 先頭見出し直後の最初の段落
2. Description / Overview / Summary 等の代表見出し配下の先頭段落
3. フォールバック（メタ由来の定型文があれば呼び出し側で付与）
"""

from __future__ import annotations

import re

_MAX_CHARS = 200
_SECTION_HEADINGS = ("description", "overview", "summary", "about")

# Markdown ノイズ除去用
_FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.DOTALL)
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_BADGE_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_INLINE_CODE_RE = re.compile(r"`([^`]*)`")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_BOLD_ITALIC_RE = re.compile(r"[*_]{1,3}([^*_]+)[*_]{1,3}")
_MULTISPACE_RE = re.compile(r"\s+")


def extract_tldr(readme: str, max_chars: int = _MAX_CHARS) -> str:
    """README 本文から TL;DR を抽出する。取得不能なら空文字。"""
    if not readme:
        return ""

    text = _FRONTMATTER_RE.sub("", readme)
    lines = text.splitlines()

    paragraph = _first_paragraph_after_heading(lines)
    if not paragraph:
        paragraph = _paragraph_under_section(lines)
    if not paragraph:
        return ""

    return _clean(paragraph, max_chars)


def _first_paragraph_after_heading(lines: list[str]) -> str:
    """先頭の見出し（# ...）の直後に現れる最初の段落を返す。"""
    seen_heading = False
    buffer: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            if seen_heading and buffer:
                break
            seen_heading = True
            continue
        if seen_heading:
            if stripped:
                buffer.append(stripped)
            elif buffer:
                break
    return " ".join(buffer)


def _paragraph_under_section(lines: list[str]) -> str:
    """代表見出し（Description 等）配下の先頭段落を返す。"""
    in_section = False
    buffer: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip().lower()
            if buffer:
                break
            in_section = any(heading.startswith(key) for key in _SECTION_HEADINGS)
            continue
        if in_section:
            if stripped:
                buffer.append(stripped)
            elif buffer:
                break
    return " ".join(buffer)


def _clean(text: str, max_chars: int) -> str:
    """Markdown 記法・バッジ・画像・過剰な空白を除去し文字数を丸める。"""
    text = _IMAGE_RE.sub("", text)
    text = _BADGE_LINK_RE.sub(r"\1", text)
    text = _INLINE_CODE_RE.sub(r"\1", text)
    text = _HTML_TAG_RE.sub("", text)
    text = _BOLD_ITALIC_RE.sub(r"\1", text)
    text = _MULTISPACE_RE.sub(" ", text).strip()

    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "…"

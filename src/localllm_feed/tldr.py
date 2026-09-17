"""README からの TL;DR ルールベース抽出（LLF-DD-001 §2.4）。

生成AIは使用しない。README から段落候補を集め、量子化配布者の定型文
（"static quants of ..." 等）を避けて最初の意味ある段落を採用する。
定型文しか無い場合は元モデル URL を抽出し、呼び出し側が元モデル README を
再取得する。取得不能なら空文字。
"""

from __future__ import annotations

import re

_MAX_CHARS = 200
_SECTION_HEADINGS = ("description", "overview", "summary", "about", "model")

# 量子化配布者の定型文（実質的な説明ではない）
_BOILERPLATE_RE = re.compile(
    r"^\s*(static|weighted|imatrix|weighted/imatrix)?\s*(gguf\s+)?quants?\s+of\b"
    r"|^\s*quantiz(ed|ations?)\s+(version|of)\b"
    r"|^\s*this\s+(is\s+)?(a\s+)?(re-?upload|mirror)\b",
    re.IGNORECASE,
)
# 元モデル URL（"... of https://huggingface.co/{author}/{repo}"）
_BASE_MODEL_RE = re.compile(
    r"of\s+https?://huggingface\.co/([A-Za-z0-9._-]+/[A-Za-z0-9._-]+)",
    re.IGNORECASE,
)

# Markdown ノイズ除去用
_FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.DOTALL)
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_MDLINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_BARE_URL_RE = re.compile(r"https?://\S+")
_INLINE_CODE_RE = re.compile(r"`([^`]*)`")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_BOLD_ITALIC_RE = re.compile(r"[*_]{1,3}([^*_]+)[*_]{1,3}")
_MULTISPACE_RE = re.compile(r"\s+")


def extract_tldr(readme: str, max_chars: int = _MAX_CHARS) -> str:
    """README 本文から TL;DR を抽出する。定型文は避ける。取得不能なら空文字。"""
    if not readme:
        return ""
    paragraphs = _candidate_paragraphs(readme)
    for para in paragraphs:
        if _is_boilerplate(para):
            continue
        cleaned = _clean(para, max_chars)
        if cleaned:
            return cleaned
    return ""


def extract_base_model_id(readme: str) -> str:
    """定型文中の元モデル ID（author/repo）を抽出する。無ければ空文字。"""
    if not readme:
        return ""
    text = _FRONTMATTER_RE.sub("", readme)
    m = _BASE_MODEL_RE.search(text)
    return m.group(1) if m else ""


def is_boilerplate_readme(readme: str) -> bool:
    """README の先頭段落が量子化配布者の定型文かどうか。"""
    paragraphs = _candidate_paragraphs(readme)
    return bool(paragraphs) and _is_boilerplate(paragraphs[0])


def _candidate_paragraphs(readme: str) -> list[str]:
    """見出し直後の段落＋代表見出し配下の段落を候補として順に返す。"""
    text = _FRONTMATTER_RE.sub("", readme)
    lines = text.splitlines()
    candidates: list[str] = []
    first = _first_paragraph_after_heading(lines)
    if first:
        candidates.append(first)
    section = _paragraph_under_section(lines)
    if section and section not in candidates:
        candidates.append(section)
    # 追加候補: 見出し直後の次段落も拾う（定型文回避のため）
    for para in _all_paragraphs(lines):
        if para not in candidates:
            candidates.append(para)
    return candidates


def _all_paragraphs(lines: list[str]) -> list[str]:
    """本文中の全段落（見出し行を除く）を出現順に返す。"""
    paras: list[str] = []
    buffer: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            if buffer:
                paras.append(" ".join(buffer))
                buffer = []
            continue
        if stripped:
            buffer.append(stripped)
        elif buffer:
            paras.append(" ".join(buffer))
            buffer = []
    if buffer:
        paras.append(" ".join(buffer))
    return paras


def _first_paragraph_after_heading(lines: list[str]) -> str:
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


def _is_boilerplate(text: str) -> bool:
    return bool(_BOILERPLATE_RE.search(text or ""))


def _clean(text: str, max_chars: int) -> str:
    """Markdown 記法・バッジ・画像・素URL・過剰な空白を除去し文字数を丸める。"""
    text = _IMAGE_RE.sub("", text)
    text = _MDLINK_RE.sub(r"\1", text)
    text = _BARE_URL_RE.sub("", text)
    text = _INLINE_CODE_RE.sub(r"\1", text)
    text = _HTML_TAG_RE.sub("", text)
    text = _BOLD_ITALIC_RE.sub(r"\1", text)
    text = _MULTISPACE_RE.sub(" ", text).strip()

    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "…"
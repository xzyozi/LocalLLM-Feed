"""HF モデル情報からのファクト抽出ヘルパー（LLF-DD-001 §2.3）。

外部依存を持たない純関数群。モデル名・タグ・ファイル一覧から
params_b / quants / is_distilled / base を導出する。生成AIは使用しない。
"""

from __future__ import annotations

import re

# 例: "-35B-", "_7b", "3.8B" などのパラメータ数表記を検出する
_PARAMS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[bB](?![a-zA-Z])")
# 量子化サフィックス（GGUF 慣例）。例: Q4_K_M, Q5_K_S, Q8_0, Q6_K, IQ4_XS
_QUANT_RE = re.compile(r"\b((?:IQ|Q)\d+(?:_[A-Z0-9]+)*)\b", re.IGNORECASE)
_DISTILL_RE = re.compile(r"distill", re.IGNORECASE)
# base 正規化で末尾から取り除く量子化/フォーマット関連の語
_BASE_STRIP_RE = re.compile(r"[-_.]?(gguf|ggml)$", re.IGNORECASE)


def extract_params_b(name: str) -> float | None:
    """モデル名からパラメータ数（十億単位）を抽出する。

    複数該当時は最大値を採用する。抽出不能なら None。
    """
    matches = _PARAMS_RE.findall(name or "")
    if not matches:
        return None
    values = [float(m) for m in matches]
    return max(values)


def extract_quants(file_names: list[str]) -> list[str]:
    """GGUF ファイル名一覧から量子化フォーマットを列挙する（重複排除・出現順）。"""
    seen: dict[str, None] = {}
    for fname in file_names:
        for m in _QUANT_RE.findall(fname or ""):
            token = m.upper()
            if token not in seen:
                seen[token] = None
    return list(seen.keys())


def is_distilled(name: str, tags: list[str] | None = None) -> bool:
    """モデル名またはタグに蒸留を示す語が含まれるか判定する。"""
    haystack = [name or ""]
    if tags:
        haystack.extend(tags)
    return any(_DISTILL_RE.search(text or "") for text in haystack)


def normalize_base(repo_name: str) -> str:
    """リポジトリ名からベースモデル名を正規化する。

    末尾の GGUF/GGML 表記を除去する。author 接頭辞は含めない前提。
    """
    base = repo_name or ""
    base = _BASE_STRIP_RE.sub("", base)
    return base.strip("-_. ")
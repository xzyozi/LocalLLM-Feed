"""HF モデル情報からのファクト抽出ヘルパー（LLF-DD-001 §2.3）。

外部依存を持たない純関数群。モデル名・タグ・ファイル一覧から
params_b / quants / is_distilled / base を導出する。生成AIは使用しない。
"""

from __future__ import annotations

import re

# 例: "-35B-", "_7b", "3.8B" などのパラメータ数表記を検出する
_PARAMS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[bB](?![a-zA-Z])")
# MoE 表記（例: "8x7B", "8X22B"）。エキスパート数 x 各エキスパートのパラメータ数。
# 名目値としては後段（各エキスパートのB数）を採用する（VRAM 概算の一貫性のため）。
_MOE_RE = re.compile(r"(\d+)\s*[xX]\s*(\d+(?:\.\d+)?)\s*[bB](?![a-zA-Z])")
# 量子化サフィックス（GGUF 慣例）。例: Q4_K_M, Q5_K_S, Q8_0, Q6_K, IQ4_XS
_QUANT_RE = re.compile(r"\b((?:IQ|Q)\d+(?:_[A-Z0-9]+)*)\b", re.IGNORECASE)
_DISTILL_RE = re.compile(r"distill", re.IGNORECASE)
# base 正規化で末尾から取り除く量子化/フォーマット関連の語
_BASE_STRIP_RE = re.compile(r"[-_.]?(gguf|ggml)$", re.IGNORECASE)


def extract_params_b(name: str) -> float | None:
    """モデル名からパラメータ数（十億単位、名目値）を抽出する。

    MoE 表記（例: "Mixtral-8x7B"）は各エキスパートのパラメータ数（7）を
    名目値として採用する。総実効パラメータではなく名目値を返すのは、
    フロントの VRAM 概算が単一の代表パラメータ数を前提とするため。
    通常表記が複数該当する場合は最大値を採用する。抽出不能なら None。

    Args:
        name: モデル名またはリポジトリ名。

    Returns:
        パラメータ数（十億単位）の名目値。抽出できなければ None。
    """
    text = name or ""
    # MoE 表記を優先的に処理し、エキスパート数（"8x" の 8）を誤って拾わないようにする。
    moe = _MOE_RE.search(text)
    if moe:
        return float(moe.group(2))
    matches = _PARAMS_RE.findall(text)
    if not matches:
        return None
    values = [float(m) for m in matches]
    return max(values)


def extract_quants(file_names: list[str]) -> list[str]:
    """GGUF ファイル名一覧から量子化フォーマットを列挙する（重複排除・出現順）。

    量子化サフィックスは `.gguf` ファイルだけから抽出する。`config-Q4.json` の
    ような非 GGUF ファイル名を量子化として誤検出しないための絞り込み。

    Args:
        file_names: リポジトリ内のファイル名一覧。

    Returns:
        出現順・重複排除済みの量子化フォーマット文字列のリスト。
    """
    seen: dict[str, None] = {}
    for fname in file_names:
        if not (fname or "").lower().endswith(".gguf"):
            continue
        for m in _QUANT_RE.findall(fname):
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

"""Hugging Face API 連携（HuggingFaceCrawler / PopularScanner）。

LLF-DD-001 §2.2（収集条件）・§3.4（失敗契約）に対応する。
HF models API から GGUF モデルのファクトを取得し ModelRecord を構築する。
ネットワーク I/O は本モジュールに閉じ、抽出ロジックは extract.py に委譲する。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from localllm_feed import extract
from localllm_feed.config import CollectionConfig
from localllm_feed.models import CandidateAuthor, ModelRecord

HF_API_BASE = "https://huggingface.co/api"
_MAX_RETRIES = 3
_BACKOFF_BASE = 1.5


@dataclass(frozen=True)
class HfModelSummary:
    """HF models API から得た1モデルの生データ（必要フィールドのみ）。"""

    id: str
    downloads: int
    last_modified: str
    tags: list[str]
    siblings: list[str]  # リポジトリ内ファイル名一覧


class HuggingFaceClient:
    """HF API への薄いラッパ。リトライ・レート制限に対応する。"""

    def __init__(self, client: httpx.Client | None = None, token: str | None = None) -> None:
        headers = {"User-Agent": "LocalLLM-Feed/0.1.0"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = client or httpx.Client(base_url=HF_API_BASE, headers=headers, timeout=30.0)

    def list_models(self, params: dict) -> list[dict]:
        """models 一覧を取得する。5xx/429/タイムアウトはリトライする。"""
        return self._get_json("/models", params)

    def _get_json(self, path: str, params: dict) -> list[dict]:
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = self._client.get(path, params=params)
                if resp.status_code == 429 or resp.status_code >= 500:
                    time.sleep(_BACKOFF_BASE ** attempt)
                    continue
                resp.raise_for_status()
                data = resp.json()
                return data if isinstance(data, list) else []
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                time.sleep(_BACKOFF_BASE ** attempt)
        if last_exc is not None:
            raise last_exc
        raise RuntimeError(f"HF API request failed after {_MAX_RETRIES} retries: {path}")

    def close(self) -> None:
        self._client.close()


def _summary_from_raw(raw: dict) -> HfModelSummary:
    siblings = [s.get("rfilename", "") for s in raw.get("siblings", []) if isinstance(s, dict)]
    return HfModelSummary(
        id=str(raw.get("id") or raw.get("modelId") or ""),
        downloads=int(raw.get("downloads", 0) or 0),
        last_modified=str(raw.get("lastModified") or ""),
        tags=list(raw.get("tags", []) or []),
        siblings=siblings,
    )


def _to_record(summary: HfModelSummary) -> ModelRecord | None:
    """HfModelSummary から ModelRecord を構築する。params_b 抽出不能なら None。"""
    if "/" not in summary.id:
        return None
    author, repo = summary.id.split("/", 1)
    params_b = extract.extract_params_b(repo) or extract.extract_params_b(summary.id)
    if params_b is None:
        return None
    quants = extract.extract_quants(summary.siblings)
    date_str = _iso_to_date(summary.last_modified)
    return ModelRecord(
        id=summary.id,
        base=extract.normalize_base(repo),
        author=author,
        date=date_str,
        params_b=params_b,
        is_distilled=extract.is_distilled(repo, summary.tags),
        quants=quants,
        downloads=summary.downloads,
        tldr="",
    )


def crawl_models(client: HuggingFaceClient, config: CollectionConfig) -> list[HfModelSummary]:
    """ホワイトリスト著者ごとに GGUF モデル一覧を取得する（DL下限フィルタ適用）。"""
    results: list[HfModelSummary] = []
    for author in config.authors:
        params = {
            "author": author,
            "sort": "lastModified",
            "direction": "-1",
            "limit": config.max_records,
            "full": "true",
        }
        if config.gguf_only:
            params["filter"] = "gguf"
        for raw in client.list_models(params):
            summary = _summary_from_raw(raw)
            if summary.downloads >= config.min_downloads:
                results.append(summary)
    return results


def scan_popular_outside_whitelist(
    client: HuggingFaceClient, config: CollectionConfig
) -> list[CandidateAuthor]:
    """gguf を人気順で走査し、ホワイトリスト外の高DL配布者を検出する。"""
    scan = config.popular_scan
    if not scan.enabled:
        return []
    params = {
        "filter": "gguf",
        "sort": "downloads",
        "direction": "-1",
        "limit": scan.scan_limit,
        "full": "false",
    }
    whitelist = {a.lower() for a in config.authors}
    seen: dict[str, CandidateAuthor] = {}
    for raw in client.list_models(params):
        summary = _summary_from_raw(raw)
        if "/" not in summary.id:
            continue
        author = summary.id.split("/", 1)[0]
        if author.lower() in whitelist:
            continue
        if summary.downloads < scan.notify_min_downloads:
            continue
        if author not in seen:
            seen[author] = CandidateAuthor(
                author=author,
                downloads=summary.downloads,
                sample_model_id=summary.id,
            )
    return list(seen.values())


def summaries_to_records(summaries: list[HfModelSummary]) -> list[ModelRecord]:
    """HfModelSummary 群を ModelRecord へ変換する（抽出不能は除外）。"""
    records: list[ModelRecord] = []
    for summary in summaries:
        rec = _to_record(summary)
        if rec is not None:
            records.append(rec)
    return records


def _iso_to_date(value: str) -> str:
    """ISO 8601 文字列を YYYY-MM-DD へ。失敗時は本日(UTC)。"""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.date().isoformat()
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc).date().isoformat()
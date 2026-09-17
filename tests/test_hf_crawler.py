"""hf_crawler モジュールの単体テスト（httpx をモック）。"""

from __future__ import annotations

import httpx

from localllm_feed import hf_crawler
from localllm_feed.config import CollectionConfig, PopularScanConfig


def _client_with(responses: dict[tuple[str, str], list[dict]]) -> hf_crawler.HuggingFaceClient:
    """(author or filter) をキーにレスポンスを返す MockTransport クライアント。"""

    def handler(request: httpx.Request) -> httpx.Response:
        author = request.url.params.get("author", "")
        sort = request.url.params.get("sort", "")
        return httpx.Response(200, json=responses.get((author, sort), []))

    transport = httpx.MockTransport(handler)
    inner = httpx.Client(base_url=hf_crawler.HF_API_BASE, transport=transport)
    return hf_crawler.HuggingFaceClient(client=inner)


def test_crawl_models_applies_min_downloads() -> None:
    responses = {
        ("bartowski", "lastModified"): [
            {"id": "bartowski/Foo-7B-GGUF", "downloads": 100, "lastModified": "2026-09-10T00:00:00Z",
             "siblings": [{"rfilename": "Foo-Q4_K_M.gguf"}]},
            {"id": "bartowski/Bar-13B-GGUF", "downloads": 5, "lastModified": "2026-09-11T00:00:00Z",
             "siblings": [{"rfilename": "Bar-Q8_0.gguf"}]},
        ],
    }
    client = _client_with(responses)
    cfg = CollectionConfig(min_downloads=50, authors=("bartowski",))
    summaries = hf_crawler.crawl_models(client, cfg)
    ids = {s.id for s in summaries}
    assert "bartowski/Foo-7B-GGUF" in ids
    assert "bartowski/Bar-13B-GGUF" not in ids
    client.close()


def test_summaries_to_records_builds_expected() -> None:
    summaries = [
        hf_crawler.HfModelSummary(
            id="bartowski/Foo-7B-GGUF",
            downloads=100,
            last_modified="2026-09-10T00:00:00Z",
            tags=[],
            siblings=["Foo-Q4_K_M.gguf", "Foo-Q8_0.gguf"],
        ),
        hf_crawler.HfModelSummary(
            id="bartowski/NoParams-GGUF",
            downloads=100,
            last_modified="2026-09-10T00:00:00Z",
            tags=[],
            siblings=["x.gguf"],
        ),
    ]
    records = hf_crawler.summaries_to_records(summaries)
    assert len(records) == 1
    rec = records[0]
    assert rec.author == "bartowski"
    assert rec.params_b == 7.0
    assert rec.quants == ["Q4_K_M", "Q8_0"]
    assert rec.date == "2026-09-10"


def test_scan_popular_excludes_whitelist_and_below_threshold() -> None:
    responses = {
        ("", "downloads"): [
            {"id": "newauthor/Cool-7B-GGUF", "downloads": 5000},
            {"id": "bartowski/Known-7B-GGUF", "downloads": 9000},
            {"id": "small/Tiny-7B-GGUF", "downloads": 100},
        ],
    }
    client = _client_with(responses)
    cfg = CollectionConfig(
        authors=("bartowski",),
        popular_scan=PopularScanConfig(enabled=True, notify_min_downloads=1000, scan_limit=100),
    )
    candidates = hf_crawler.scan_popular_outside_whitelist(client, cfg)
    authors = {c.author for c in candidates}
    assert "newauthor" in authors
    assert "bartowski" not in authors
    assert "small" not in authors
    client.close()


def test_scan_disabled_returns_empty() -> None:
    client = _client_with({})
    cfg = CollectionConfig(popular_scan=PopularScanConfig(enabled=False))
    assert hf_crawler.scan_popular_outside_whitelist(client, cfg) == []
    client.close()
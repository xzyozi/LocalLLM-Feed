"""hf_crawler モジュールの単体テスト（httpx をモック）。"""

from __future__ import annotations

import httpx

from localllm_feed import hf_crawler
from localllm_feed.config import CollectionConfig, PopularScanConfig
from localllm_feed.models import ModelRecord


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
            {
                "id": "bartowski/Foo-7B-GGUF",
                "downloads": 100,
                "lastModified": "2026-09-10T00:00:00Z",
                "siblings": [{"rfilename": "Foo-Q4_K_M.gguf"}],
            },
            {
                "id": "bartowski/Bar-13B-GGUF",
                "downloads": 5,
                "lastModified": "2026-09-11T00:00:00Z",
                "siblings": [{"rfilename": "Bar-Q8_0.gguf"}],
            },
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


def _readme_client(readme_by_id: dict[str, str]) -> hf_crawler.HuggingFaceClient:
    """README 取得をモックするクライアント。URL 末尾の README.md に応答する。"""

    def handler(request):
        url = str(request.url)
        for model_id, body in readme_by_id.items():
            if f"/{model_id}/raw/main/README.md" in url:
                return httpx.Response(200, text=body)
        return httpx.Response(404, text="")

    transport = httpx.MockTransport(handler)
    inner = httpx.Client(transport=transport)
    return hf_crawler.HuggingFaceClient(client=inner)


def _rec(rec_id: str) -> ModelRecord:
    return ModelRecord(id=rec_id, base=rec_id, author="a", date="2026-09-10", params_b=7.0)


def test_enrich_with_tldr_fills_top_n() -> None:
    records = [_rec("a/M1-7B-GGUF"), _rec("a/M2-7B-GGUF"), _rec("a/M3-7B-GGUF")]
    readmes = {
        "a/M1-7B-GGUF": "# M1\n\nFirst great model for chat.",
        "a/M2-7B-GGUF": "# M2\n\nSecond model overview.",
        "a/M3-7B-GGUF": "# M3\n\nThird model.",
    }
    client = _readme_client(readmes)
    out = hf_crawler.enrich_with_tldr(client, records, limit=2)
    assert "First great model" in out[0].tldr
    assert "Second model overview" in out[1].tldr
    assert out[2].tldr == ""  # limit=2 のため 3件目は据え置き
    client.close()


def test_enrich_with_tldr_limit_zero_noop() -> None:
    records = [_rec("a/M1-7B-GGUF")]
    client = _readme_client({"a/M1-7B-GGUF": "# M1\n\ntext"})
    out = hf_crawler.enrich_with_tldr(client, records, limit=0)
    assert out[0].tldr == ""
    client.close()


def test_enrich_with_tldr_missing_readme_kept_empty() -> None:
    records = [_rec("a/NoReadme-7B-GGUF")]
    client = _readme_client({})  # 404 を返す
    out = hf_crawler.enrich_with_tldr(client, records, limit=5)
    assert out[0].tldr == ""
    client.close()
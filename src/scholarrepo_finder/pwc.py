"""Papers with Code公開アーカイブのリポジトリ照合クライアント。"""

from typing import Optional
from urllib.parse import urlsplit

import httpx

from scholarrepo_finder.models import PapersWithCodeMatch

PWC_ARCHIVE_DATASET = "pwc-archive/links-between-paper-and-code"
PWC_DATASET_FILTER_URL = "https://datasets-server.huggingface.co/filter"


def _repository_url_variants(repository_url: str) -> list[str]:
    """GitHub URLの末尾スラッシュと.git差を吸収した照合候補を返す。"""
    parsed = urlsplit(repository_url)
    path = parsed.path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    canonical = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"
    return [canonical, f"{canonical}/", f"{canonical}.git"]


class PapersWithCodeClient:
    """Hugging Face上のPWC最終公開アーカイブを参照するクライアント.

    HTTP接続はインスタンス生成時に確立した単一の `httpx.Client` を再利用する。
    Step 2では `lookup_repository` が収集件数分（実測932件）だけ逐次呼び出される
    ため、呼び出しごとに新規クライアントを生成・破棄する従来実装はTCP/TLSハンド
    シェイクの反復コストが大きい（`GitHubCollector` に対するPR #10と同種の改善）。
    呼び出し元は `close()` を呼ぶか、コンテキストマネージャとして使うこと。
    """

    def __init__(self, timeout: float = 15.0, client: Optional[httpx.Client] = None) -> None:
        self.timeout = timeout
        # 外部から共有クライアントを渡された場合は所有権を持たず、closeでは破棄しない。
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=self.timeout)

    def close(self) -> None:
        """自身が生成したHTTPクライアントの接続を解放する."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "PapersWithCodeClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def lookup_repository(self, repository_url: str) -> PapersWithCodeMatch:
        """GitHubリポジトリURLに紐づくPWC登録を照合する。"""
        variants = _repository_url_variants(repository_url)
        escaped_variants = [value.replace("'", "''") for value in variants]
        where = " OR ".join(f"repo_url = '{value}'" for value in escaped_variants)
        params: dict[str, str | int] = {
            "dataset": PWC_ARCHIVE_DATASET,
            "config": "default",
            "split": "train",
            "where": where,
            "offset": 0,
            "length": 100,
        }
        try:
            response = self._client.get(PWC_DATASET_FILTER_URL, params=params)
        except httpx.HTTPError:
            return PapersWithCodeMatch(lookup_status="failed")

        if response.status_code != 200:
            return PapersWithCodeMatch(lookup_status="failed")

        data = response.json()
        rows = data.get("rows", []) if isinstance(data, dict) else []
        records = [row.get("row", row) for row in rows if isinstance(row, dict)]
        if not records:
            return PapersWithCodeMatch(lookup_status="not_found")

        selected = next((record for record in records if record.get("is_official") is True), records[0])
        is_official = bool(selected.get("is_official"))
        return PapersWithCodeMatch(
            lookup_status="matched_official" if is_official else "matched_unofficial",
            is_official=is_official,
            repository_url=variants[0],
            paper_url=selected.get("paper_url_abs") or selected.get("paper_url"),
            arxiv_id=selected.get("paper_arxiv_id"),
        )

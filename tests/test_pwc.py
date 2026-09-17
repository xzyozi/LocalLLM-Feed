"""Papers with Codeアーカイブ照合クライアントの公開契約テスト。"""

from unittest.mock import MagicMock, patch

from scholarrepo_finder.pwc import PapersWithCodeClient


@patch("httpx.Client.get")
def test_lookup_repository_prefers_official_pwc_archive_match(mock_get: MagicMock) -> None:
    """同一リポジトリの候補から公式登録を優先して返す。"""
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "rows": [
            {"row": {"repo_url": "https://github.com/lab/tool", "is_official": False}},
            {
                "row": {
                    "repo_url": "https://github.com/lab/tool",
                    "is_official": True,
                    "paper_url_abs": "https://arxiv.org/abs/2401.00001",
                    "paper_arxiv_id": "2401.00001",
                }
            },
        ]
    }
    mock_get.return_value = response

    match = PapersWithCodeClient().lookup_repository("https://github.com/lab/tool.git")

    assert match.lookup_status == "matched_official"
    assert match.is_official is True
    assert match.repository_url == "https://github.com/lab/tool"
    assert match.paper_url == "https://arxiv.org/abs/2401.00001"
    assert mock_get.call_args.args[0] == "https://datasets-server.huggingface.co/filter"


@patch("httpx.Client.get")
def test_lookup_repository_distinguishes_not_found_from_service_failure(mock_get: MagicMock) -> None:
    """照合対象なしと外部サービス障害を同じ未登録扱いにしない。"""
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"rows": []}
    mock_get.return_value = response

    client = PapersWithCodeClient()
    assert client.lookup_repository("https://github.com/lab/missing").lookup_status == "not_found"

    response.status_code = 503
    assert client.lookup_repository("https://github.com/lab/unavailable").lookup_status == "failed"


def test_close_closes_owned_client() -> None:
    """close() が自身の生成したHTTPクライアントの接続を解放する。"""
    client = PapersWithCodeClient()
    client.close()

    assert client._client.is_closed is True


def test_shared_client_is_not_closed_by_pwc_client() -> None:
    """外部から注入した共有クライアントは、close() では破棄されない。"""
    import httpx

    shared_client = httpx.Client(timeout=5.0)
    client = PapersWithCodeClient(client=shared_client)
    client.close()

    assert shared_client.is_closed is False
    shared_client.close()


@patch("httpx.Client.get")
def test_lookup_repository_reuses_shared_client_across_calls(mock_get: MagicMock) -> None:
    """複数回のlookup_repository呼び出しで同一クライアントインスタンスが使われる。"""
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"rows": []}
    mock_get.return_value = response

    client = PapersWithCodeClient()
    client_instance_before = client._client
    client.lookup_repository("https://github.com/lab/one")
    client.lookup_repository("https://github.com/lab/two")

    assert client._client is client_instance_before
    assert mock_get.call_count == 2

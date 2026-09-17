"""データ収集モジュールの単体テスト (モック検証)."""

import base64
import threading
from typing import List
from unittest.mock import MagicMock, patch

import httpx

from scholarrepo_finder.collector import ApiCallObserver, GitHubCollector, format_observer_summary
from scholarrepo_finder.models import GitHubOwnerProfile


@patch("httpx.Client.get")
def test_search_repositories_success(mock_get: MagicMock) -> None:
    """search_repositories の正常系レスポンスパース検証."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "items": [
            {"full_name": "owner/repo1", "name": "repo1"},
            {"full_name": "owner/repo2", "name": "repo2"},
        ]
    }
    mock_get.return_value = mock_resp

    collector = GitHubCollector(token="dummy_token")
    results = collector.search_repositories("topic:simulation")
    assert len(results) == 2
    assert results[0]["full_name"] == "owner/repo1"


@patch("httpx.Client.get")
def test_fetch_readme_base64(mock_get: MagicMock) -> None:
    """fetch_readme での Base64 デコード動作検証."""
    readme_text = "# Test Repository\nThis is a simulation benchmark."
    encoded = base64.b64encode(readme_text.encode("utf-8")).decode("utf-8")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "content": encoded,
        "encoding": "base64",
    }
    mock_get.return_value = mock_resp

    collector = GitHubCollector(token="dummy_token")
    result = collector.fetch_readme("owner/repo")
    assert result == readme_text


@patch("httpx.Client.get")
def test_fetch_file_tree(mock_get: MagicMock) -> None:
    """fetch_file_tree のパース検証."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "tree": [
            {"path": "src/main.py", "type": "blob"},
            {"path": "tests/test_main.py", "type": "blob"},
            {"path": "README.md", "type": "blob"},
        ]
    }
    mock_get.return_value = mock_resp

    collector = GitHubCollector(token="dummy_token")
    tree = collector.fetch_file_tree("owner/repo")
    assert "src/main.py" in tree
    assert "tests/test_main.py" in tree


@patch.object(GitHubCollector, "fetch_readme")
@patch.object(GitHubCollector, "fetch_file_tree")
@patch.object(GitHubCollector, "fetch_dependency_files")
def test_fetch_repository_details(
    mock_dep: MagicMock, mock_tree: MagicMock, mock_readme: MagicMock
) -> None:
    """fetch_repository_details による RepoRaw 構築検証."""
    mock_readme.return_value = "# Repo\nSimulation content."
    mock_tree.return_value = ["src/app.py", "requirements.txt"]
    mock_dep.return_value = {"requirements.txt": "numpy>=1.20"}

    repo_data = {
        "full_name": "lab/sim-opt",
        "name": "sim-opt",
        "owner": {"login": "lab"},
        "description": "Simulation and Optimization toolkit",
        "html_url": "https://github.com/lab/sim-opt",
        "default_branch": "main",
        "stargazers_count": 42,
        "forks_count": 5,
        "created_at": "2024-01-01T00:00:00Z",
        "pushed_at": "2024-06-01T12:00:00Z",
        "license": {"spdx_id": "MIT"},
        "language": "Python",
        "topics": ["simulation", "optimization"],
    }

    collector = GitHubCollector(token="dummy")
    raw = collector.fetch_repository_details(repo_data)
    assert raw is not None
    assert raw.repo_id == "lab/sim-opt"
    assert raw.stars == 42
    assert raw.license_spdx == "MIT"
    assert "numpy>=1.20" in raw.dependency_files.get("requirements.txt", "")


@patch("httpx.Client.get")
def test_fetch_owner_profile_normalizes_organization_data(mock_get: MagicMock) -> None:
    """組織プロフィールから安全な信頼度評価用属性だけを正規化する。"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "login": "research-lab",
        "email": "contact@research-lab.edu",
        "created_at": "2018-01-01T00:00:00Z",
        "is_verified": True,
    }
    mock_get.return_value = mock_response

    profile = GitHubCollector(token="dummy").fetch_owner_profile("research-lab", "Organization")

    assert profile.login == "research-lab"
    assert profile.account_type == "Organization"
    assert profile.email_domain == "research-lab.edu"
    assert profile.is_verified_org is True
    assert profile.account_age_years >= 5
    assert profile.lookup_status == "found"
    assert mock_get.call_args.args[0] == "https://api.github.com/orgs/research-lab"


@patch.object(GitHubCollector, "fetch_readme", return_value="README")
@patch.object(GitHubCollector, "fetch_file_tree", return_value=[])
@patch.object(GitHubCollector, "fetch_dependency_files", return_value={})
@patch.object(
    GitHubCollector,
    "fetch_owner_profile",
    return_value=GitHubOwnerProfile(
        login="research-lab",
        account_type="Organization",
        email_domain="research-lab.edu",
        is_verified_org=True,
        account_age_years=8,
        lookup_status="found",
    ),
)
def test_fetch_repository_details_attaches_owner_profile(
    mock_owner: MagicMock,
    mock_dependencies: MagicMock,
    mock_tree: MagicMock,
    mock_readme: MagicMock,
) -> None:
    """リポジトリ詳細が所有者エンリッチメントを生データに保持する。"""
    raw = GitHubCollector(token="dummy").fetch_repository_details(
        {
            "full_name": "research-lab/toolkit",
            "name": "toolkit",
            "owner": {"login": "research-lab", "type": "Organization"},
        }
    )

    assert raw is not None
    assert raw.owner_profile is not None
    assert raw.owner_profile.email_domain == "research-lab.edu"
    mock_owner.assert_called_once_with("research-lab", "Organization")


def test_fetch_repository_details_fetches_readme_tree_and_owner_concurrently() -> None:
    """README・ファイルツリー・所有者情報の取得が並列実行されることを検証する。

    threading.Barrier を用いて、3つの呼び出しが同一タイミングで揃って実行
    されていることを決定的に確認する (タイミング計測による不安定なテストを避ける)。
    逐次実行のままだと3スレッドが同時にバリアへ到達できずタイムアウトする。
    """
    barrier = threading.Barrier(3, timeout=5.0)
    call_order: List[str] = []
    lock = threading.Lock()

    def record(name: str) -> None:
        with lock:
            call_order.append(name)
        barrier.wait()

    collector = GitHubCollector(token="dummy")

    def fake_fetch_readme(repo_id: str) -> str:
        record("readme")
        return "README"

    def fake_fetch_file_tree(repo_id: str, default_branch: str = "main") -> List[str]:
        record("file_tree")
        return []

    def fake_fetch_owner_profile(owner_login: str, owner_type: str) -> GitHubOwnerProfile:
        record("owner_profile")
        return GitHubOwnerProfile(login=owner_login, account_type=owner_type)

    collector.fetch_readme = fake_fetch_readme  # type: ignore[method-assign]
    collector.fetch_file_tree = fake_fetch_file_tree  # type: ignore[method-assign]
    collector.fetch_owner_profile = fake_fetch_owner_profile  # type: ignore[method-assign]
    collector.fetch_dependency_files = MagicMock(return_value={})  # type: ignore[method-assign]

    try:
        raw = collector.fetch_repository_details(
            {
                "full_name": "lab/sim-opt",
                "name": "sim-opt",
                "owner": {"login": "lab", "type": "User"},
            }
        )
    finally:
        collector.close()

    assert raw is not None
    assert sorted(call_order) == ["file_tree", "owner_profile", "readme"]


def test_close_shuts_down_detail_executor_and_owned_client() -> None:
    """close() が自身の詳細取得用スレッドプールと、自身が生成したHTTPクライアントを解放する。"""
    collector = GitHubCollector(token="dummy")
    collector.close()

    # shutdown後のスレッドプールへのsubmitはRuntimeErrorになる (concurrent.futures の公開契約)。
    try:
        collector._detail_executor.submit(lambda: None)
        raised = False
    except RuntimeError:
        raised = True
    assert raised is True
    assert collector._client.is_closed is True


def test_shared_client_is_not_closed_by_collector() -> None:
    """外部から注入した共有クライアントは、collector.close() では破棄されない。"""
    shared_client = httpx.Client(timeout=5.0)
    collector = GitHubCollector(token="dummy", client=shared_client)
    collector.close()

    assert shared_client.is_closed is False
    shared_client.close()


def test_api_call_observer_classifies_primary_rate_limit() -> None:
    """X-RateLimit-Remaining: 0 の403をプライマリのレート制限として分類する。"""
    observer = ApiCallObserver()
    headers = httpx.Headers({"X-RateLimit-Remaining": "0"})

    observer.record("readme", 403, headers)

    assert observer.summary() == {"readme": {"rate_limit_primary": 1}}
    assert observer.has_rate_limit_hits() is True


def test_api_call_observer_classifies_secondary_rate_limit() -> None:
    """レート制限枠が残っているのに403/429が返る場合はSecondary rate limit相当として分類する。"""
    observer = ApiCallObserver()
    headers = httpx.Headers({"X-RateLimit-Remaining": "500"})

    observer.record("file_tree", 403, headers)
    observer.record("owner_profile", 429, None)

    summary = observer.summary()
    assert summary["file_tree"]["rate_limit_secondary_or_abuse"] == 1
    assert summary["owner_profile"]["rate_limit_secondary_or_abuse"] == 1
    assert observer.has_rate_limit_hits() is True


def test_api_call_observer_classifies_success_and_exception() -> None:
    """200は成功、ステータスコードなし(None)は例外として分類し、レート制限扱いにしない。"""
    observer = ApiCallObserver()

    observer.record("readme", 200, httpx.Headers({}))
    observer.record("owner_profile", None)

    summary = observer.summary()
    assert summary["readme"] == {"success": 1}
    assert summary["owner_profile"] == {"exception": 1}
    assert observer.has_rate_limit_hits() is False


def test_format_observer_summary_warns_on_rate_limit() -> None:
    """レート制限を検出した場合、警告メッセージを含めて整形する。"""
    observer = ApiCallObserver()
    observer.record("readme", 403, httpx.Headers({"X-RateLimit-Remaining": "0"}))

    output = format_observer_summary(observer)

    assert "readme" in output
    assert "rate_limit_primary=1" in output
    assert "⚠️" in output


def test_format_observer_summary_without_records() -> None:
    """記録がない場合は「記録なし」を返す。"""
    observer = ApiCallObserver()

    output = format_observer_summary(observer)

    assert "記録なし" in output


@patch("httpx.Client.get")
def test_search_repositories_records_observer(mock_get: MagicMock) -> None:
    """search_repositories がAPI呼び出し結果をobserverへ記録する。"""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = httpx.Headers({})
    mock_resp.json.return_value = {"items": []}
    mock_get.return_value = mock_resp

    collector = GitHubCollector(token="dummy_token")
    collector.search_repositories("topic:simulation")

    assert collector.observer.summary() == {"search": {"success": 1}}


def test_api_call_observer_detects_core_rate_limit_and_records_reset_time() -> None:
    """core枠切れ(readme/file_tree/dependency_files/owner_profile)を検出し、リセット時刻を保持する。"""
    observer = ApiCallObserver()
    reset_epoch = "1735689600"  # 2025-01-01T00:00:00+00:00
    headers = httpx.Headers({"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": reset_epoch})

    assert observer.is_core_rate_limited() is False

    observer.record("readme", 403, headers)

    assert observer.is_core_rate_limited() is True
    reset_at = observer.rate_limit_reset_at()
    assert reset_at is not None
    assert reset_at.year == 2025


def test_api_call_observer_search_rate_limit_does_not_trigger_core_cutoff() -> None:
    """Search APIのレート制限は別枠のため、coreの早期打ち切りフラグを立てない。"""
    observer = ApiCallObserver()
    headers = httpx.Headers({"X-RateLimit-Remaining": "0"})

    observer.record("search", 403, headers)

    assert observer.has_rate_limit_hits() is True
    assert observer.is_core_rate_limited() is False


def test_fetch_readme_skips_request_when_core_rate_limited() -> None:
    """core枠切れ後、fetch_readmeはHTTPリクエストを送らずNoneを返す。"""
    collector = GitHubCollector(token="dummy")
    collector.observer.record("file_tree", 403, httpx.Headers({"X-RateLimit-Remaining": "0"}))
    assert collector.observer.is_core_rate_limited() is True

    with patch("httpx.Client.get") as mock_get:
        result = collector.fetch_readme("owner/repo")

    assert result is None
    mock_get.assert_not_called()


def test_fetch_file_tree_skips_request_when_core_rate_limited() -> None:
    """core枠切れ後、fetch_file_treeはHTTPリクエストを送らず空リストを返す。"""
    collector = GitHubCollector(token="dummy")
    collector.observer.record("readme", 403, httpx.Headers({"X-RateLimit-Remaining": "0"}))

    with patch("httpx.Client.get") as mock_get:
        result = collector.fetch_file_tree("owner/repo")

    assert result == []
    mock_get.assert_not_called()


def test_fetch_dependency_files_skips_request_when_core_rate_limited() -> None:
    """core枠切れ後、fetch_dependency_filesはHTTPリクエストを送らず空辞書を返す。"""
    collector = GitHubCollector(token="dummy")
    collector.observer.record("owner_profile", 403, httpx.Headers({"X-RateLimit-Remaining": "0"}))

    with patch("httpx.Client.get") as mock_get:
        result = collector.fetch_dependency_files("owner/repo", ["requirements.txt"])

    assert result == {}
    mock_get.assert_not_called()


def test_fetch_owner_profile_skips_request_when_core_rate_limited() -> None:
    """core枠切れ後、fetch_owner_profileはHTTPリクエストを送らずskipped_rate_limitedを返す。"""
    collector = GitHubCollector(token="dummy")
    collector.observer.record("readme", 403, httpx.Headers({"X-RateLimit-Remaining": "0"}))

    with patch("httpx.Client.get") as mock_get:
        profile = collector.fetch_owner_profile("someone", "User")

    assert profile.lookup_status == "skipped_rate_limited"
    mock_get.assert_not_called()


def test_fetch_repository_details_returns_none_and_notes_skip_when_core_rate_limited() -> None:
    """core枠切れ後、fetch_repository_detailsはリポジトリをNoneとして除外し、スキップ件数を記録する。"""
    collector = GitHubCollector(token="dummy")
    collector.observer.record("readme", 403, httpx.Headers({"X-RateLimit-Remaining": "0"}))

    with patch("httpx.Client.get") as mock_get:
        raw = collector.fetch_repository_details({"full_name": "owner/repo", "owner": {"login": "owner"}})

    assert raw is None
    assert collector.observer.skipped_due_to_rate_limit_count() == 1
    mock_get.assert_not_called()


def test_format_observer_summary_reports_cutoff_and_skip_count() -> None:
    """早期打ち切り発生時、format_observer_summaryにスキップ件数とリセット予定を含める。"""
    observer = ApiCallObserver()
    reset_epoch = "1735689600"
    observer.record("readme", 403, httpx.Headers({"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": reset_epoch}))
    observer.note_skipped_due_to_rate_limit()
    observer.note_skipped_due_to_rate_limit()

    output = format_observer_summary(observer)

    assert "🛑" in output
    assert "スキップしたリポジトリ数: 2件" in output
    assert "2025-01-01" in output

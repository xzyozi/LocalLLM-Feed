"""ScholarRepo-Finder データ収集モジュール (Data Ingestion)."""

import base64
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
import threading
from typing import Any, Dict, List, Optional

import httpx

from scholarrepo_finder.models import GitHubOwnerProfile, RepoRaw

DEFAULT_SEED_TOPICS = [
    # 数理最適化・OR
    "operations-research",
    "vehicle-routing",
    "combinatorial-optimization",
    "linear-programming",
    "integer-programming",
    "mixed-integer-linear-programming",
    "mathematical-optimization",
    "constraint-programming",
    # シミュレーション & モデリング
    "discrete-event-simulation",
    "agent-based-modeling",
    "multi-agent-systems",
    "traffic-simulation",
    "supply-chain-optimization",
    "cellular-automata",
    "complex-systems",
    "monte-carlo-simulation",
    "stochastic-simulation",
    # アルゴリズム検証 & 機械学習/科学計算
    "reinforcement-learning",
    "deep-reinforcement-learning",
    "graph-neural-networks",
    "scientific-computing",
    "computational-physics",
    "numerical-simulation",
    "evolutionary-algorithms",
    "genetic-algorithm",
    "bayesian-optimization",
    "surrogate-modeling",
    "finite-element-analysis",
    "computational-fluid-dynamics",
]

DEFAULT_SEED_QUERIES = [
    '"arxiv.org/abs" "simulation"',
    '"doi.org" "benchmark"',
    '"baseline algorithm" "reproduce"',
    '"operations research" "algorithm" "benchmark"',
    '"agent-based" "simulation" "benchmark"',
    '"combinatorial optimization" "dataset"',
    '"reinforcement learning" "environment" "simulation"',
    '"discrete-event" "simulation" "python"',
]

DEPENDENCY_FILE_CANDIDATES = [
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "Pipfile",
    "Cargo.toml",
    "package.json",
    "CMakeLists.txt",
]

SEED_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "operations_research": [
        "operations research",
        "operations-research",
        "vehicle-routing",
        "combinatorial-optimization",
        "linear-programming",
        "integer-programming",
        "mathematical-optimization",
        "constraint-programming",
    ],
    "simulation": [
        "simulation",
        "agent-based",
        "multi-agent",
        "traffic",
        "cellular-automata",
        "monte-carlo",
        "stochastic",
        "discrete-event",
    ],
    "numerical_computing": [
        "scientific-computing",
        "computational-physics",
        "numerical",
        "finite-element",
        "computational-fluid",
    ],
    "machine_learning": [
        "reinforcement-learning",
        "reinforcement learning",
        "graph-neural",
        "evolutionary-algorithms",
        "genetic-algorithm",
        "bayesian-optimization",
        "surrogate-modeling",
    ],
}


# README・ファイルツリー・依存定義・所有者情報の各エンドポイントは、GitHubの
# "core" レート制限枠を共有する。一方 search_repositories が使う Search API は
# 別枠のレート制限を持つため、coreの枠切れを検出してもsearchの呼び出しは
# 妨げない。 https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
CORE_RATE_LIMIT_ENDPOINTS = frozenset({"readme", "file_tree", "dependency_files", "owner_profile"})


class ApiCallObserver:
    """GitHub API呼び出しの成否・レート制限抵触を集計する観測クラス.

    `GitHubCollector` の並列化（複数スレッドから同一クライアントを共有）により、
    以前より短時間に多くのリクエストが集中する。レート制限やその他の失敗が
    サイレントに増えていないかを可視化するため、エンドポイント種別ごとに
    ステータスを集計する。複数スレッドから呼ばれるため `threading.Lock` で保護する。

    また、"core" レート制限枠切れを検出した場合はその状態を保持し、
    `GitHubCollector` の各メソッドが以降の無駄なHTTPリクエストを送らずに
    早期打ち切りできるようにする（実測でcore枠切れ後も762回分のリクエストを
    送り続けてしまい、全て失敗する事象を確認したため）。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._core_rate_limited = False
        self._rate_limit_reset_at: Optional[datetime] = None
        self._skipped_due_to_rate_limit = 0

    def record(self, endpoint: str, status_code: Optional[int], headers: Optional[httpx.Headers] = None) -> None:
        """1回のAPI呼び出し結果を記録する.

        Args:
            endpoint: 呼び出し元を識別するラベル（search / readme / file_tree /
                dependency_files / owner_profile）。
            status_code: HTTPステータスコード。例外発生時は None を渡す。
            headers: レスポンスヘッダー（`httpx.Response.headers`）。403時に
                `X-RateLimit-Remaining` を見てプライマリ/セカンダリのレート制限を
                区別するために使う。
        """
        category = self._classify(status_code, headers)
        with self._lock:
            self._counts[endpoint][category] += 1
            if (
                category == "rate_limit_primary"
                and endpoint in CORE_RATE_LIMIT_ENDPOINTS
                and not self._core_rate_limited
            ):
                self._core_rate_limited = True
                self._rate_limit_reset_at = self._parse_reset_at(headers)

    @staticmethod
    def _classify(status_code: Optional[int], headers: Optional[httpx.Headers]) -> str:
        if status_code is None:
            return "exception"
        if status_code == 200:
            return "success"
        if status_code == 404:
            return "not_found"
        if status_code == 403 or status_code == 429:
            remaining = headers.get("X-RateLimit-Remaining") if headers is not None else None
            if remaining == "0":
                return "rate_limit_primary"
            # プライマリのレート制限枠が残っているのに403/429が返る場合は、
            # 同時実行数の急増によるSecondary rate limitの可能性が高い。
            return "rate_limit_secondary_or_abuse"
        return f"other_failure_{status_code}"

    @staticmethod
    def _parse_reset_at(headers: Optional[httpx.Headers]) -> Optional[datetime]:
        """`X-RateLimit-Reset`(UNIX epoch秒)をUTCのdatetimeへ変換する."""
        if headers is None:
            return None
        reset_epoch = headers.get("X-RateLimit-Reset")
        if not reset_epoch:
            return None
        try:
            return datetime.fromtimestamp(int(reset_epoch), tz=timezone.utc)
        except (TypeError, ValueError):
            return None

    def summary(self) -> Dict[str, Dict[str, int]]:
        """エンドポイントごとの集計結果のスナップショットを返す."""
        with self._lock:
            return {endpoint: dict(categories) for endpoint, categories in self._counts.items()}

    def has_rate_limit_hits(self) -> bool:
        """いずれかのエンドポイントでレート制限に抵触したかを返す."""
        with self._lock:
            return any(
                category.startswith("rate_limit") and count > 0
                for categories in self._counts.values()
                for category, count in categories.items()
            )

    def is_core_rate_limited(self) -> bool:
        """coreレート制限枠が切れており、以降の詳細取得を打ち切るべきかを返す."""
        with self._lock:
            return self._core_rate_limited

    def rate_limit_reset_at(self) -> Optional[datetime]:
        """coreレート制限のリセット予定時刻(UTC)を返す。未検出または不明な場合はNone."""
        with self._lock:
            return self._rate_limit_reset_at

    def note_skipped_due_to_rate_limit(self) -> None:
        """レート制限により詳細取得をスキップしたリポジトリを1件記録する."""
        with self._lock:
            self._skipped_due_to_rate_limit += 1

    def skipped_due_to_rate_limit_count(self) -> int:
        """レート制限により詳細取得をスキップしたリポジトリ数を返す."""
        with self._lock:
            return self._skipped_due_to_rate_limit


def classify_seed_categories(seed: str) -> List[str]:
    """シードトピックまたは検索クエリから分野カテゴリを判定する."""
    normalized_seed = seed.lower()
    categories = [
        category
        for category, keywords in SEED_CATEGORY_KEYWORDS.items()
        if any(keyword in normalized_seed for keyword in keywords)
    ]
    return categories or ["unclassified"]


class GitHubCollector:
    """GitHub API から学術・シミュレーションリポジトリを収集するクライアント.

    HTTP接続はインスタンス生成時に確立した単一の `httpx.Client` を全メソッドで
    再利用する。1件あたり複数回のGitHub API呼び出しが発生するため、呼び出しごとに
    クライアントを生成・破棄する従来実装はTCP/TLSハンドシェイクの反復コストが
    大きい。呼び出し元は `close()` を呼ぶか、コンテキストマネージャとして使うこと。
    """

    def __init__(
        self,
        token: Optional[str] = None,
        timeout: float = 15.0,
        client: Optional[httpx.Client] = None,
        max_detail_workers: int = 3,
        observer: Optional[ApiCallObserver] = None,
    ) -> None:
        self.token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        self.timeout = timeout
        self.headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "ScholarRepo-Finder/0.1.0",
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"
        # 外部から共有クライアントを渡された場合は所有権を持たず、closeでは破棄しない。
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=self.timeout)
        self.observer = observer or ApiCallObserver()
        # fetch_repository_details内の独立したAPI呼び出し(README・ファイルツリー・
        # 所有者情報)を並列実行するためのスレッドプール。httpx.Clientはスレッドセーフ
        # であり、単一インスタンス共有の方が接続プーリング効率も良い
        # (https://github.com/encode/httpx/discussions/1633)。
        self._detail_executor = ThreadPoolExecutor(max_workers=max_detail_workers, thread_name_prefix="ghc-detail")

    def close(self) -> None:
        """自身が生成したスレッドプールとHTTPクライアントの接続をすべて解放する."""
        self._detail_executor.shutdown(wait=True)
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "GitHubCollector":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def search_repositories(
        self, query: str, sort: str = "stars", order: str = "desc", per_page: int = 30
    ) -> List[Dict[str, Any]]:
        """GitHub Search API を用いてリポジトリ候補を検索する."""
        url = "https://api.github.com/search/repositories"
        params: dict[str, str | int] = {"q": query, "sort": sort, "order": order, "per_page": per_page}

        resp = self._client.get(url, headers=self.headers, params=params)
        self.observer.record("search", resp.status_code, resp.headers)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("items", [])
        elif resp.status_code == 403:
            # Rate limit
            return []
        return []

    def fetch_readme(self, repo_id: str) -> Optional[str]:
        """リポジトリの README テキストを取得する.

        coreレート制限枠が切れている場合はリクエストを送らずNoneを返す
        (無駄なリクエストで枠切れ後も失敗を積み重ねないための早期打ち切り)。
        """
        if self.observer.is_core_rate_limited():
            return None
        url = f"https://api.github.com/repos/{repo_id}/readme"
        resp = self._client.get(url, headers=self.headers)
        self.observer.record("readme", resp.status_code, resp.headers)
        if resp.status_code == 200:
            data = resp.json()
            content = data.get("content", "")
            encoding = data.get("encoding", "")
            if encoding == "base64":
                try:
                    return base64.b64decode(content).decode("utf-8", errors="replace")
                except Exception:
                    return None
            return content
        return None

    def fetch_file_tree(self, repo_id: str, default_branch: str = "main") -> List[str]:
        """リポジトリのファイルツリーを取得する (Git Trees API).

        coreレート制限枠が切れている場合はリクエストを送らず空リストを返す。
        """
        if self.observer.is_core_rate_limited():
            return []
        url = f"https://api.github.com/repos/{repo_id}/git/trees/{default_branch}?recursive=1"
        resp = self._client.get(url, headers=self.headers)
        self.observer.record("file_tree", resp.status_code, resp.headers)
        if resp.status_code == 200:
            tree_data = resp.json().get("tree", [])
            return [item.get("path", "") for item in tree_data if "path" in item]
        return []

    def fetch_dependency_files(self, repo_id: str, file_tree: List[str]) -> Dict[str, str]:
        """主要な依存定義ファイルの内容を取得する.

        coreレート制限枠が切れている場合はリクエストを送らず空辞書を返す。
        """
        dep_files: Dict[str, str] = {}
        if self.observer.is_core_rate_limited():
            return dep_files
        target_files = [f for f in file_tree if os.path.basename(f) in DEPENDENCY_FILE_CANDIDATES]

        for filepath in target_files[:5]:  # 最大5ファイルまでに制限
            if self.observer.is_core_rate_limited():
                break
            url = f"https://api.github.com/repos/{repo_id}/contents/{filepath}"
            resp = self._client.get(url, headers=self.headers)
            self.observer.record("dependency_files", resp.status_code, resp.headers)
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("content", "")
                encoding = data.get("encoding", "")
                if encoding == "base64":
                    try:
                        dep_files[filepath] = base64.b64decode(content).decode("utf-8", errors="replace")
                    except Exception:
                        pass
        return dep_files

    def fetch_owner_profile(self, owner_login: str, owner_type: str) -> GitHubOwnerProfile:
        """GitHub所有者を照会し、公開メールのドメインだけを安全に保持する.

        coreレート制限枠が切れている場合はリクエストを送らず、
        `lookup_status="skipped_rate_limited"` のフォールバックを返す。
        """
        account_type = owner_type or "Unknown"
        endpoint = "orgs" if account_type.lower() == "organization" else "users"
        fallback = GitHubOwnerProfile(login=owner_login, account_type=account_type)
        if self.observer.is_core_rate_limited():
            return fallback.model_copy(update={"lookup_status": "skipped_rate_limited"})
        url = f"https://api.github.com/{endpoint}/{owner_login}"

        try:
            response = self._client.get(url, headers=self.headers)
        except httpx.HTTPError:
            self.observer.record("owner_profile", None)
            return fallback.model_copy(update={"lookup_status": "failed"})

        self.observer.record("owner_profile", response.status_code, response.headers)
        if response.status_code == 404:
            return fallback.model_copy(update={"lookup_status": "not_found"})
        if response.status_code != 200:
            return fallback.model_copy(update={"lookup_status": "failed"})

        data = response.json()
        created_at = data.get("created_at")
        try:
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00")) if created_at else None
        except (AttributeError, ValueError):
            created = None
        account_age_years = max(0, (datetime.now(timezone.utc) - created).days // 365) if created else 0
        email = data.get("email")
        email_domain = email.rsplit("@", 1)[-1].lower() if isinstance(email, str) and "@" in email else None

        return GitHubOwnerProfile(
            login=data.get("login") or owner_login,
            account_type=account_type,
            email_domain=email_domain,
            is_verified_org=account_type.lower() == "organization" and bool(data.get("is_verified")),
            account_age_years=account_age_years,
            lookup_status="found",
        )

    def fetch_repository_details(self, repo_data: Dict[str, Any]) -> Optional[RepoRaw]:
        """検索結果の 1 レコードから詳細な RepoRaw オブジェクトを構築する.

        README・ファイルツリー・所有者情報の取得は互いに独立したGitHub API呼び出し
        であり、いずれもネットワーク応答待ちが支配的なI/Oバウンド処理のため、
        スレッドプールで並列実行してレイテンシを重ね合わせる。依存定義ファイルの
        取得はファイルツリーの結果に依存するため、並列化の対象外とし逐次実行する。
        """
        repo_id = repo_data.get("full_name", "")
        if not repo_id:
            return None

        if self.observer.is_core_rate_limited():
            # core枠切れ後は各fetchメソッドがガードにより空値を返すため、
            # README・ファイルツリー等が全て欠落した空のRepoRawを作らず、
            # このリポジトリ自体を収集対象から除外する。
            self.observer.note_skipped_due_to_rate_limit()
            return None

        default_branch = repo_data.get("default_branch", "main")

        owner_info = repo_data.get("owner") or {}
        owner_name = owner_info.get("login", "") if isinstance(owner_info, dict) else ""
        owner_type = owner_info.get("type", "Unknown") if isinstance(owner_info, dict) else "Unknown"

        readme_future = self._detail_executor.submit(self.fetch_readme, repo_id)
        file_tree_future = self._detail_executor.submit(self.fetch_file_tree, repo_id, default_branch)
        owner_profile_future = (
            self._detail_executor.submit(self.fetch_owner_profile, owner_name, owner_type) if owner_name else None
        )

        readme = readme_future.result()
        file_tree = file_tree_future.result()
        owner_profile = owner_profile_future.result() if owner_profile_future else None

        dep_files = self.fetch_dependency_files(repo_id, file_tree)

        created_at_str = repo_data.get("created_at")
        updated_at_str = repo_data.get("pushed_at") or repo_data.get("updated_at")

        created_at = (
            datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            if created_at_str
            else datetime.now(timezone.utc)
        )
        last_commit_at = (
            datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
            if updated_at_str
            else datetime.now(timezone.utc)
        )

        license_info = repo_data.get("license") or {}
        license_spdx = license_info.get("spdx_id") if isinstance(license_info, dict) else None

        return RepoRaw(
            repo_id=repo_id,
            name=repo_data.get("name", ""),
            owner=owner_name,
            owner_profile=owner_profile,
            description=repo_data.get("description"),
            html_url=repo_data.get("html_url", f"https://github.com/{repo_id}"),
            default_branch=default_branch,
            stars=repo_data.get("stargazers_count", 0),
            forks=repo_data.get("forks_count", 0),
            created_at=created_at,
            last_commit_at=last_commit_at,
            license_spdx=license_spdx,
            primary_language=repo_data.get("language"),
            topics=repo_data.get("topics", []),
            readme_raw=readme,
            file_tree=file_tree,
            dependency_files=dep_files,
        )


def format_observer_summary(observer: ApiCallObserver) -> str:
    """観測結果を標準出力向けの1ブロックに整形する.

    レート制限に1件でも抵触していれば警告として強調し、成功/失敗が判別しやすい
    形式にする。Step 1完了後にログへ出すことで、収集件数や掲載件数の変化が
    API側の失敗によるものかどうかを判断できるようにする。coreレート制限枠切れに
    より収集を早期打ち切りした場合は、スキップ件数とリセット予定時刻も表示する。
    """
    summary = observer.summary()
    if not summary:
        return "   -> API呼び出し観測: 記録なし"

    lines = ["   -> API呼び出し観測:"]
    for endpoint in sorted(summary):
        categories = summary[endpoint]
        total = sum(categories.values())
        detail = ", ".join(f"{category}={count}" for category, count in sorted(categories.items()))
        lines.append(f"      - {endpoint}: 合計{total}回 ({detail})")

    if observer.has_rate_limit_hits():
        lines.append("      ⚠️  レート制限への抵触を検出しました。掲載件数・収集品質への影響を確認してください。")

    if observer.is_core_rate_limited():
        skipped = observer.skipped_due_to_rate_limit_count()
        reset_at = observer.rate_limit_reset_at()
        reset_text = reset_at.isoformat() if reset_at else "不明"
        lines.append(
            f"      🛑 coreレート制限枠切れのため、以降の詳細取得を打ち切りました"
            f"（スキップしたリポジトリ数: {skipped}件、リセット予定: {reset_text}）。"
        )

    return "\n".join(lines)


def collect_seed_repositories(
    collector: GitHubCollector,
    topics: Optional[List[str]] = None,
    queries: Optional[List[str]] = None,
    limit_per_query: int = 10,
) -> List[RepoRaw]:
    """定義済みシードから候補を収集し、候補ごとのシードカテゴリを保持する."""
    from time import perf_counter

    collection_started_at = perf_counter()
    target_topics = topics or DEFAULT_SEED_TOPICS
    target_queries = queries or DEFAULT_SEED_QUERIES
    collected_repos: Dict[str, RepoRaw] = {}

    def collect_items(items: List[Dict[str, Any]], seed_categories: List[str]) -> None:
        """検索結果を重複排除しつつ、見つかったシードカテゴリを候補へ統合する."""
        for item in items:
            repo_id = item.get("full_name")
            if not repo_id:
                continue

            existing = collected_repos.get(repo_id)
            if existing:
                existing.seed_categories = sorted(set(existing.seed_categories) | set(seed_categories))
                continue

            raw = collector.fetch_repository_details(item)
            if raw:
                raw.seed_categories = sorted(set(seed_categories))
                collected_repos[repo_id] = raw
                if len(collected_repos) % 100 == 0:
                    elapsed_seconds = perf_counter() - collection_started_at
                    print(f"   -> Step 1: {len(collected_repos)} 件の詳細を取得済み ({elapsed_seconds:.1f} 秒経過)")

    for topic in target_topics:
        items = collector.search_repositories(f"topic:{topic}", per_page=limit_per_query)
        collect_items(items, classify_seed_categories(topic))

    for query in target_queries:
        items = collector.search_repositories(query, per_page=limit_per_query)
        collect_items(items, classify_seed_categories(query))

    return list(collected_repos.values())

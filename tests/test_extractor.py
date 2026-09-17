"""特徴抽出モジュールの単体テスト."""

from datetime import datetime

from scholarrepo_finder.extractor import (
    calculate_academic_keyword_score,
    detect_scientific_libraries,
    extract_features,
    is_academic_email_domain,
)
from scholarrepo_finder.models import GitHubOwnerProfile, PapersWithCodeMatch, RepoRaw


def test_is_academic_email_domain() -> None:
    """アカデミックドメイン判定の検証."""
    assert is_academic_email_domain("researcher@mit.edu") is True
    assert is_academic_email_domain("prof@u-tokyo.ac.jp") is True
    assert is_academic_email_domain("dr@ox.ac.uk") is True
    assert is_academic_email_domain("scientist@nasa.gov") is True
    assert is_academic_email_domain("user@gmail.com") is False
    assert is_academic_email_domain("dev@company.com") is False
    assert is_academic_email_domain(None) is False


def test_detect_scientific_libraries() -> None:
    """依存ファイルおよびTopicsからの科学計算ライブラリ検出検証."""
    dep_files = {
        "requirements.txt": "numpy>=1.24.0\nscipy==1.10.0\nortools>=9.5\nflask==2.2.0",
        "pyproject.toml": 'dependencies = ["simpy>=4.0", "networkx"]',
    }
    topics = ["operations-research", "pulp", "simulation"]
    libs = detect_scientific_libraries(dep_files, topics)
    assert "numpy" in libs
    assert "scipy" in libs
    assert "ortools" in libs
    assert "simpy" in libs
    assert "networkx" in libs
    assert "pulp" in libs
    assert "flask" not in libs


def test_calculate_academic_keyword_score() -> None:
    """学術キーワードスコアの算出検証."""
    text = "We provide experimental results on benchmark datasets and baseline simulation algorithms."
    score = calculate_academic_keyword_score(text)
    assert score > 0.0
    assert score <= 10.0

    empty_score = calculate_academic_keyword_score("")
    assert empty_score == 0.0


def test_extract_features_comprehensive() -> None:
    """extract_features の網羅的動作検証."""
    now = datetime.now()
    raw = RepoRaw(
        repo_id="stanford-lab/cvrp-deep-solver",
        name="cvrp-deep-solver",
        owner="stanford-lab",
        description="A benchmark simulation for vehicle routing problems.",
        html_url="https://github.com/stanford-lab/cvrp-deep-solver",
        stars=50,
        forks=10,
        created_at=now,
        last_commit_at=now,
        license_spdx="MIT",
        primary_language="Python",
        topics=["vehicle-routing", "simulation", "ortools"],
        readme_raw="""
# CVRP Deep Solver
Paper available at https://arxiv.org/abs/2405.12345
DOI: https://doi.org/10.1016/j.orl.2024.100000
Includes benchmark datasets and experimental results.
        """,
        file_tree=[
            "src/solver.py",
            "tests/test_solver.py",
            "docs/index.md",
            ".github/workflows/ci.yml",
            "requirements.txt",
        ],
        dependency_files={
            "requirements.txt": "numpy>=1.20\ntorch>=2.0\nortools>=9.0",
        },
        owner_profile=GitHubOwnerProfile(
            login="stanford-lab",
            account_type="Organization",
            email_domain="stanford.edu",
            is_verified_org=True,
            account_age_years=5,
            lookup_status="found",
        ),
        pwc_match=PapersWithCodeMatch(
            lookup_status="matched_official",
            is_official=True,
            repository_url="https://github.com/stanford-lab/cvrp-deep-solver",
        ),
    )

    features = extract_features(raw)

    assert features.repo_id == "stanford-lab/cvrp-deep-solver"
    assert features.has_src_or_app_dir is True
    assert features.has_tests_dir is True
    assert features.has_docs_dir is True
    assert features.has_ci_workflow is True
    assert "numpy" in features.scientific_libs_detected
    assert "torch" in features.scientific_libs_detected
    assert "ortools" in features.scientific_libs_detected
    assert features.has_doi_link is True
    assert features.has_arxiv_link is True
    assert features.is_pwc_official is True
    assert features.academic_keyword_score > 0.0
    assert features.is_edu_or_ac_domain is True
    assert features.is_verified_org is True
    assert features.author_account_age_years == 5

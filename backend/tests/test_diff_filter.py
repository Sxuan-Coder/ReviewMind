from app.schemas.diff import PullRequestFile
from app.services.diff_filter import filter_diff_files, get_exclude_reason


def make_file(filename: str, additions: int = 1, deletions: int = 1) -> PullRequestFile:
    return PullRequestFile(
        filename=filename,
        status="modified",
        additions=additions,
        deletions=deletions,
        patch="@@ -1 +1 @@",
    )


def test_filter_lock_files() -> None:
    result = filter_diff_files([make_file("frontend/package-lock.json")])

    assert result.included_files == []
    assert result.excluded_files[0].exclude_reason == "lock file is excluded"


def test_filter_build_directories() -> None:
    result = filter_diff_files([make_file("dist/index.js"), make_file("build/app.css")])

    assert len(result.excluded_files) == 2
    assert all(item.exclude_reason == "generated build output is excluded" for item in result.excluded_files)


def test_filter_static_assets() -> None:
    result = filter_diff_files([make_file("assets/logo.png"), make_file("public/icon.svg")])

    assert len(result.excluded_files) == 2
    assert all(item.exclude_reason == "static or minified asset is excluded" for item in result.excluded_files)


def test_keep_source_files_and_count_totals() -> None:
    result = filter_diff_files([
        make_file("backend/app/main.py", additions=5, deletions=2),
        make_file("frontend/src/App.tsx", additions=8, deletions=1),
        make_file("yarn.lock", additions=100, deletions=100),
    ])

    assert [file.filename for file in result.included_files] == [
        "backend/app/main.py",
        "frontend/src/App.tsx",
    ]
    assert result.total_additions == 13
    assert result.total_deletions == 3


def test_get_exclude_reason_handles_windows_separator() -> None:
    reason = get_exclude_reason("frontend\\dist\\bundle.js")

    assert reason == "generated build output is excluded"


def test_minified_files_are_filtered_case_insensitively() -> None:
    reason = get_exclude_reason("public/VENDOR.MIN.JS")

    assert reason == "static or minified asset is excluded"
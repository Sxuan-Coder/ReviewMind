from app.schemas.diff import PullRequestFile
from app.services.diff_parser import parse_diff_file


def test_parse_single_hunk_added_lines() -> None:
    file = PullRequestFile(
        filename="src/app.py",
        status="modified",
        additions=2,
        deletions=1,
        patch="@@ -1,3 +1,4 @@\n import os\n-old = 1\n+new = 1\n+extra = 2\n done = True",
    )

    result = parse_diff_file(file)

    assert result.file == "src/app.py"
    assert result.changed_lines == [2, 3]
    assert result.deleted_lines == [2]
    assert len(result.hunks) == 1


def test_parse_multiple_hunks() -> None:
    file = PullRequestFile(
        filename="src/app.py",
        patch="@@ -1 +1 @@\n-old\n+new\n@@ -10,2 +10,3 @@\n context\n+added",
    )

    result = parse_diff_file(file)

    assert len(result.hunks) == 2
    assert result.changed_lines == [1, 11]
    assert result.deleted_lines == [1]


def test_empty_patch_returns_empty_hunks() -> None:
    file = PullRequestFile(filename="src/new.py", status="added", additions=0, deletions=0, patch=None)

    result = parse_diff_file(file)

    assert result.hunks == []
    assert result.changed_lines == []
    assert result.deleted_lines == []


def test_parse_deleted_file_lines() -> None:
    file = PullRequestFile(
        filename="src/old.py",
        status="removed",
        additions=0,
        deletions=2,
        patch="@@ -4,2 +0,0 @@\n-old one\n-old two",
    )

    result = parse_diff_file(file)

    assert result.changed_lines == []
    assert result.deleted_lines == [4, 5]


def test_ignore_no_newline_marker() -> None:
    file = PullRequestFile(
        filename="src/app.py",
        patch="@@ -1 +1 @@\n-old\n+new\n\\ No newline at end of file",
    )

    result = parse_diff_file(file)

    assert result.changed_lines == [1]
    assert result.deleted_lines == [1]
    assert len(result.hunks[0].lines) == 2


def test_support_renamed_file_metadata() -> None:
    file = PullRequestFile(
        filename="src/new_name.py",
        status="renamed",
        additions=1,
        deletions=0,
        patch="@@ -1 +1,2 @@\n same\n+new",
    )

    result = parse_diff_file(file)

    assert result.status == "renamed"
    assert result.file == "src/new_name.py"
    assert result.changed_lines == [2]
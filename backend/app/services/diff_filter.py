from fnmatch import fnmatch
from pathlib import PurePosixPath

from app.schemas.diff import DiffFilterResult, ExcludedDiffFile, PullRequestFile

LOCK_FILES = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock"}
BUILD_DIRECTORIES = {"dist", "build"}
BINARY_OR_STATIC_PATTERNS = (
    "*.min.js",
    "*.min.css",
    "*.svg",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.ico",
)


def filter_diff_files(files: list[PullRequestFile]) -> DiffFilterResult:
    included_files: list[PullRequestFile] = []
    excluded_files: list[ExcludedDiffFile] = []

    for file in files:
        exclude_reason = get_exclude_reason(file.filename)
        if exclude_reason:
            excluded_files.append(ExcludedDiffFile(file=file, exclude_reason=exclude_reason))
        else:
            included_files.append(file)

    return DiffFilterResult(
        included_files=included_files,
        excluded_files=excluded_files,
        total_additions=sum(file.additions for file in included_files),
        total_deletions=sum(file.deletions for file in included_files),
    )


def get_exclude_reason(filename: str) -> str | None:
    normalized_filename = filename.replace("\\", "/").lstrip("/")
    basename = PurePosixPath(normalized_filename).name

    if basename in LOCK_FILES:
        return "lock file is excluded"

    if any(part in BUILD_DIRECTORIES for part in normalized_filename.split("/")[:-1]):
        return "generated build output is excluded"

    if any(fnmatch(basename.lower(), pattern) for pattern in BINARY_OR_STATIC_PATTERNS):
        return "static or minified asset is excluded"

    return None
"""Data processing: summaries, search, largest files, duplicates, empty items."""

import fnmatch
import hashlib
import os
from collections import defaultdict

from .categories import all_categories

HASH_CHUNK = 64 * 1024


def human_size(num_bytes):
    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024 or unit == "GB":
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def summary(scan_result):
    files = scan_result.files
    by_category = {c: {"count": 0, "size": 0} for c in all_categories()}
    by_extension = defaultdict(lambda: {"count": 0, "size": 0})
    for f in files:
        by_category[f.category]["count"] += 1
        by_category[f.category]["size"] += f.size
        ext = f.extension or "(none)"
        by_extension[ext]["count"] += 1
        by_extension[ext]["size"] += f.size
    return {
        "files": len(files),
        "folders": len(scan_result.folders),
        "total_size": scan_result.total_size,
        "average_size": round(scan_result.total_size / len(files)) if files else 0,
        "by_category": {c: v for c, v in by_category.items() if v["count"]},
        "by_extension": dict(sorted(by_extension.items(), key=lambda kv: -kv[1]["size"])),
        "newest": max(files, key=lambda f: f.modified, default=None),
        "oldest": min(files, key=lambda f: f.modified, default=None),
        "errors": len(scan_result.errors),
    }


def sort_files(files, key="name", descending=False):
    keys = {
        "name": lambda f: f.name.lower(),
        "size": lambda f: f.size,
        "date": lambda f: f.modified,
        "type": lambda f: (f.category, f.extension, f.name.lower()),
    }
    return sorted(files, key=keys[key], reverse=descending)


def largest(files, n=10):
    return sort_files(files, "size", descending=True)[:n]


def search(files, pattern="*", extensions=None, min_size=None, max_size=None,
           modified_after=None, modified_before=None):
    """Filter files. All criteria are optional and combined with AND.
    Name matching is case-insensitive and uses wildcards (* and ?)."""
    pattern = (pattern or "*").lower()
    results = []
    for f in files:
        if not fnmatch.fnmatchcase(f.name.lower(), pattern):
            continue
        if extensions and f.extension not in extensions:
            continue
        if min_size is not None and f.size < min_size:
            continue
        if max_size is not None and f.size > max_size:
            continue
        if modified_after is not None and f.modified < modified_after:
            continue
        if modified_before is not None and f.modified > modified_before:
            continue
        results.append(f)
    return results


def file_hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(HASH_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_duplicates(files):
    """Groups of files with identical content.

    Files are first grouped by size (cheap); only same-size files are hashed.
    Returns (groups, errors). Each group is sorted so the file to keep is first
    (shallowest folder, then shortest name, so
    originals win over 'copy' / '(old)' versions). Empty files are ignored.
    """
    by_size = defaultdict(list)
    for f in files:
        if f.size > 0:
            by_size[f.size].append(f)

    groups, errors = [], []
    for candidates in by_size.values():
        if len(candidates) < 2:
            continue
        by_hash = defaultdict(list)
        for f in candidates:
            try:
                by_hash[file_hash(f.path)].append(f)
            except OSError as exc:
                errors.append(f"Cannot read {f.path}: {exc.strerror}")
        for same in by_hash.values():
            if len(same) > 1:
                groups.append(sorted(same, key=lambda f: (len(f.path.parts), len(f.name), f.name.lower())))
    groups.sort(key=lambda g: -g[0].size * (len(g) - 1))
    return groups, errors


def wasted_space(groups):
    return sum(g[0].size * (len(g) - 1) for g in groups)


def empty_files(files):
    return [f for f in files if f.size == 0]


def empty_folders(scan_result):
    """Folders with no files anywhere beneath them, deepest first."""
    empty = []
    for folder in sorted(scan_result.folders, key=lambda p: len(p.parts), reverse=True):
        try:
            entries = os.listdir(folder)
        except OSError:
            continue
        if all((folder / e) in empty for e in entries):
            empty.append(folder)
    return empty

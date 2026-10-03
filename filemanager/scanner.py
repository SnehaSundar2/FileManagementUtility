"""Walks a folder and collects information about every file.

Unreadable folders or files are recorded in ScanResult.errors instead
of stopping the scan.
"""

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .categories import category_for

# Internal items created by the utility itself; never scanned or touched.
TRASH_DIR = ".fmu_trash"
JOURNAL_FILE = ".fmu_journal.json"
INTERNAL_NAMES = {TRASH_DIR, JOURNAL_FILE}


@dataclass
class FileInfo:
    path: Path
    size: int
    modified: datetime

    @property
    def name(self):
        return self.path.name

    @property
    def extension(self):
        return self.path.suffix.lower()

    @property
    def category(self):
        return category_for(self.extension)

    def relative_to(self, root):
        return self.path.relative_to(root).as_posix()


@dataclass
class ScanResult:
    root: Path
    files: list = field(default_factory=list)
    folders: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    @property
    def total_size(self):
        return sum(f.size for f in self.files)


def scan(root, recursive=True):
    root = Path(root).resolve()
    result = ScanResult(root)

    def on_error(exc):
        result.errors.append(f"Cannot open {exc.filename}: {exc.strerror}")

    for dirpath, dirnames, filenames in os.walk(root, onerror=on_error):
        dirnames[:] = sorted(d for d in dirnames if d not in INTERNAL_NAMES)
        current = Path(dirpath)
        if current != root:
            result.folders.append(current)
        for name in sorted(filenames):
            if current == root and name in INTERNAL_NAMES:
                continue
            path = current / name
            try:
                st = path.stat()
            except OSError as exc:
                result.errors.append(f"Cannot read {path}: {exc.strerror}")
                continue
            result.files.append(FileInfo(path, st.st_size, datetime.fromtimestamp(st.st_mtime)))
        if not recursive:
            break
    return result

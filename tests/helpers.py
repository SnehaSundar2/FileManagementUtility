"""Shared fixtures: every test works inside its own temporary folder."""

import tempfile
import unittest
from pathlib import Path


class TempFolderTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()

    def make(self, rel, content=b"x"):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode())
        return path

    def names(self, folder=None):
        """Sorted relative paths of all files (excluding utility internals)."""
        folder = folder or self.root
        return sorted(p.relative_to(self.root).as_posix() for p in folder.rglob("*")
                      if p.is_file() and not p.relative_to(self.root).as_posix().startswith(".fmu"))

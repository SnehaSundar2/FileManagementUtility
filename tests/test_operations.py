import json
import shutil
from unittest.mock import patch

from filemanager import analysis
from filemanager.exceptions import (
    ConflictError,
    NothingToDoError,
    OperationError,
    UndoError,
    UnsafePathError,
    ValidationError,
)
from filemanager.operations import FileManager, Step
from filemanager.scanner import scan
from tests.helpers import TempFolderTest


class OpsTest(TempFolderTest):
    def setUp(self):
        super().setUp()
        self.fm = FileManager(self.root)

    def top_files(self):
        return scan(self.root, recursive=False).files


class TestOrganise(OpsTest):
    def test_organise_and_undo(self):
        self.make("a.jpg")
        self.make("b.pdf")
        self.make("c.unknown")
        self.make("keep/d.jpg")  # not top level: untouched
        self.fm.execute(self.fm.plan_organize(self.top_files()), "Organise")
        self.assertEqual(self.names(), ["Documents/b.pdf", "Images/a.jpg", "Other/c.unknown", "keep/d.jpg"])
        self.fm.undo_last()
        self.assertEqual(self.names(), ["a.jpg", "b.pdf", "c.unknown", "keep/d.jpg"])
        self.assertFalse((self.root / "Images").exists())  # created folders tidied up

    def test_name_clash_gets_numbered(self):
        self.make("Images/a.jpg", b"existing")
        self.make("a.jpg", b"new")
        self.fm.execute(self.fm.plan_organize(self.top_files()), "Organise")
        self.assertEqual(self.names(), ["Images/a (1).jpg", "Images/a.jpg"])
        self.assertEqual((self.root / "Images/a.jpg").read_bytes(), b"existing")

    def test_nothing_to_organise(self):
        with self.assertRaises(NothingToDoError):
            self.fm.plan_organize(self.top_files())


class TestRename(OpsTest):
    def setUp(self):
        super().setUp()
        for n in ["b.txt", "a.txt", "C.TXT"]:
            self.make(n, n)

    def plan(self, *args, **kwargs):
        return self.fm.plan_rename(self.top_files(), *args, **kwargs)

    def test_modes(self):
        self.assertEqual([s.dst.name for s in self.plan("prefix", "2026_")],
                         ["2026_a.txt", "2026_b.txt", "2026_C.TXT"])
        self.assertEqual([s.dst.name for s in self.plan("suffix", "_v2")],
                         ["a_v2.txt", "b_v2.txt", "C_v2.TXT"])
        self.assertEqual([s.dst.name for s in self.plan("sequence", "doc", start=9)],
                         ["doc_009.txt", "doc_010.txt", "doc_011.TXT"])  # extension kept
        self.assertEqual([s.dst.name for s in self.plan("lower")], ["c.txt"])  # unchanged skipped
        self.assertEqual([s.dst.name for s in self.plan("replace", "b", "beta")], ["beta.txt"])

    def test_rename_executes_and_undoes(self):
        self.fm.execute(self.plan("prefix", "x_"), "Rename")
        self.assertEqual(self.names(), ["x_C.TXT", "x_a.txt", "x_b.txt"])
        self.fm.undo_last()
        self.assertEqual(self.names(), ["C.TXT", "a.txt", "b.txt"])

    def test_case_only_rename(self):
        self.fm.execute(self.plan("lower"), "Lower")
        self.assertIn("c.txt", self.names())
        self.assertEqual((self.root / "c.txt").read_text(), "C.TXT")

    def test_conflicts_detected_and_nothing_changed(self):
        self.make("new_a.txt", "existing")
        files = [f for f in self.top_files() if f.name == "a.txt"]
        with self.assertRaises(ConflictError) as ctx:
            self.fm.plan_rename(files, "prefix", "new_")
        self.assertIn("already exists", str(ctx.exception))
        with self.assertRaises(ConflictError):  # two files -> same name
            self.plan("replace", "a", "b")

    def test_chained_rename_does_not_overwrite(self):
        """a->b while b->c: must go through temp names so b's content survives."""
        for p in list(self.root.iterdir()):
            p.unlink()
        self.make("file_001.txt", "one")
        self.make("file_002.txt", "two")
        steps = self.fm.plan_rename(self.top_files(), "sequence", "file", start=2)
        self.fm.execute(steps, "Renumber")
        self.assertEqual((self.root / "file_002.txt").read_text(), "one")
        self.assertEqual((self.root / "file_003.txt").read_text(), "two")
        self.fm.undo_last()
        self.assertEqual((self.root / "file_001.txt").read_text(), "one")
        self.assertEqual((self.root / "file_002.txt").read_text(), "two")

    def test_invalid_rename_inputs(self):
        for args in [("bogus",), ("prefix", ""), ("prefix", "bad/"), ("sequence", "CON"),
                     ("replace", "", "x")]:
            with self.assertRaises((ValidationError, NothingToDoError), msg=args):
                self.plan(*args)


class TestCopyTrashUndo(OpsTest):
    def test_copy_and_undo(self):
        self.make("a.txt", "A")
        self.make("sub/a.txt", "B")
        self.fm.execute(self.fm.plan_copy(scan(self.root).files, "backup"), "Copy")
        self.assertEqual(self.names(self.root / "backup"), ["backup/a (1).txt", "backup/a.txt"])
        self.assertTrue((self.root / "a.txt").exists())  # originals stay
        self.fm.undo_last()
        self.assertFalse((self.root / "backup").exists())

    def test_copy_folder_must_be_valid_and_inside(self):
        self.make("a.txt")
        with self.assertRaises(ValidationError):
            self.fm.plan_copy(scan(self.root).files, "../escape")
        with self.assertRaises(UnsafePathError):
            self.fm.execute([Step(self.root / "a.txt", self.root.parent / "x.txt", "copy")], "Bad")

    def test_trash_duplicates_restore_and_purge(self):
        self.make("photo.jpg", "same")
        self.make("photo copy.jpg", "same")
        groups, _ = analysis.find_duplicates(scan(self.root).files)
        self.fm.execute(self.fm.plan_trash_duplicates(groups), "Trash duplicates")
        self.assertEqual(self.names(), ["photo.jpg"])
        self.assertEqual(self.fm.trash_contents()[0], 1)
        self.fm.undo_last()
        self.assertEqual(self.names(), ["photo copy.jpg", "photo.jpg"])

        self.fm.execute(self.fm.plan_trash_duplicates(groups), "Trash duplicates")
        self.assertEqual(self.fm.purge_trash()[0], 1)
        self.assertEqual(self.fm.history(), [])  # trash ops can no longer be undone
        with self.assertRaises(NothingToDoError):
            self.fm.purge_trash()

    def test_undo_refuses_when_files_changed(self):
        self.make("a.jpg")
        self.fm.execute(self.fm.plan_organize(self.top_files()), "Organise")
        (self.root / "Images/a.jpg").unlink()
        with self.assertRaises(UndoError):
            self.fm.undo_last()

    def test_undo_with_empty_history(self):
        with self.assertRaises(UndoError):
            self.fm.undo_last()

    def test_failure_rolls_back_completed_moves(self):
        self.make("a.jpg")
        self.make("b.jpg")
        self.make("c.jpg")
        steps = self.fm.plan_organize(self.top_files())
        real_move, calls = shutil.move, []

        def flaky_move(src, dst):
            calls.append(src)
            if len(calls) == 2:
                raise PermissionError(13, "Access is denied")
            return real_move(src, dst)

        with patch("filemanager.operations.shutil.move", side_effect=flaky_move):
            with self.assertRaises(OperationError) as ctx:
                self.fm.execute(steps, "Organise")
        self.assertIn("rolled back", str(ctx.exception))
        self.assertEqual(self.names(), ["a.jpg", "b.jpg", "c.jpg"])
        self.assertEqual(self.fm.history(), [])

    def test_corrupt_journal_is_ignored(self):
        self.fm.journal_path.write_text("{not json")
        self.assertEqual(self.fm.history(), [])
        self.make("a.jpg")
        self.fm.execute(self.fm.plan_organize(self.top_files()), "Organise")
        self.assertEqual(len(json.loads(self.fm.journal_path.read_text())), 1)


if __name__ == "__main__":
    import unittest
    unittest.main()

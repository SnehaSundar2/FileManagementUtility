"""Reports, demo generator and end-to-end CLI sessions."""

import csv
import io
from contextlib import redirect_stdout
from unittest.mock import patch

from filemanager import reports
from filemanager.cli import FileManagerCLI
from filemanager.demo import DEMO_FILES, create_demo
from filemanager.exceptions import ValidationError
from filemanager.scanner import scan
from tests.helpers import TempFolderTest


def run_cli(cli, inputs):
    out = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(out):
        cli.run()
    return out.getvalue()


class TestDemoAndReports(TempFolderTest):
    def setUp(self):
        super().setUp()
        self.demo = create_demo(self.root / "demo")

    def test_demo_created_and_protected(self):
        self.assertEqual(len(scan(self.demo).files), len(DEMO_FILES))
        with self.assertRaises(ValidationError):
            create_demo(self.demo)  # refuses non-empty folder

    def test_text_report_sections(self):
        text = reports.build_text_report(scan(self.demo))
        for part in ["OVERVIEW", "BY CATEGORY", "LARGEST", "3 group(s)", "keep   holiday photo.jpg",
                     "Empty files (1): todo.txt", "old stuff"]:
            self.assertIn(part, text)

    def test_csv_inventory(self):
        path = reports.export_inventory_csv(scan(self.demo), self.root / "out" / "list.csv")
        with open(path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), len(DEMO_FILES))
        self.assertIn("projects/code/app.js", {r["path"] for r in rows})


class TestCLI(TempFolderTest):
    def setUp(self):
        super().setUp()
        self.demo = create_demo(self.root / "demo")

    def test_organise_cancel_then_confirm_then_undo(self):
        cli = FileManagerCLI(self.demo)
        out = run_cli(cli, ["7", "n", "7", "y", "12", "y", "0"])
        self.assertIn("Cancelled. Nothing was changed.", out)
        self.assertIn("moved into category folders. Use option 12 to undo.", out)
        self.assertIn("Undone: Organise by type", out)
        self.assertTrue((self.demo / "notes.txt").exists())

    def test_invalid_input_is_reported(self):
        out = run_cli(FileManagerCLI(self.demo), [
            "99",                                   # bad menu option
            "3", "*", "", "big", "",                # bad size
            "8", "*.txt", "", "sequence", "a/b", "1",  # invalid base name
            "12",                                   # nothing to undo
            "0",
        ])
        self.assertIn("Invalid option", out)
        self.assertIn("Minimum size must look like", out)
        self.assertIn("invalid character", out)
        self.assertIn("nothing to undo", out)

    def test_folder_prompt_retries_until_valid(self):
        cli = FileManagerCLI()
        out = run_cli(cli, [str(self.root / "missing"), str(self.demo), "1", "0"])
        self.assertIn("does not exist", out)
        self.assertIn("Files: 18", out)

    def test_empty_trash_needs_typed_confirmation(self):
        cli = FileManagerCLI(self.demo)
        out = run_cli(cli, ["10", "y", "14", "yes", "14", "DELETE", "0"])
        self.assertIn("This CANNOT be undone", out)
        self.assertIn("Cancelled.", out)
        self.assertIn("Permanently deleted 3 file(s).", out)

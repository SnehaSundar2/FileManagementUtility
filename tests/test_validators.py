import unittest
from datetime import datetime

from filemanager import validators as v
from filemanager.exceptions import UnsafePathError, ValidationError
from tests.helpers import TempFolderTest


class TestValidators(unittest.TestCase):
    def test_filename_valid(self):
        self.assertEqual(v.validate_filename("report 2026.pdf"), "report 2026.pdf")

    def test_filename_invalid(self):
        for bad in ["", "a/b.txt", "what?.txt", 'say"hi"', "CON", "nul.txt", "ends.", "ends ", "..",
                    "x" * 256, "tab\there"]:
            with self.assertRaises(ValidationError, msg=bad):
                v.validate_filename(bad)

    def test_name_fragment(self):
        self.assertEqual(v.validate_name_fragment("_v2"), "_v2")
        self.assertEqual(v.validate_name_fragment(""), "")
        with self.assertRaises(ValidationError):
            v.validate_name_fragment("a*b")

    def test_parse_size(self):
        self.assertEqual(v.parse_size("500"), 500)
        self.assertEqual(v.parse_size("10kb"), 10240)
        self.assertEqual(v.parse_size("1.5 MB"), 1572864)
        self.assertEqual(v.parse_size("2GB"), 2 * 1024 ** 3)
        for bad in ["", "ten", "-5MB", "5 PB", "1.2.3KB"]:
            with self.assertRaises(ValidationError):
                v.parse_size(bad)

    def test_date(self):
        self.assertEqual(v.validate_date("2026-02-28"), datetime(2026, 2, 28))
        for bad in ["2026-02-30", "28-02-2026", "yesterday"]:
            with self.assertRaises(ValidationError):
                v.validate_date(bad)

    def test_extensions(self):
        self.assertEqual(v.validate_extensions("jpg, .PNG  pdf"), {".jpg", ".png", ".pdf"})
        self.assertEqual(v.validate_extensions(""), set())
        with self.assertRaises(ValidationError):
            v.validate_extensions("jp*g")

    def test_pattern(self):
        self.assertEqual(v.validate_pattern(""), "*")
        self.assertEqual(v.validate_pattern(" *.txt "), "*.txt")
        with self.assertRaises(ValidationError):
            v.validate_pattern("sub/*.txt")

    def test_positive_int_and_choice(self):
        self.assertEqual(v.validate_positive_int("7", "N"), 7)
        for bad in ["0", "abc", "1000"]:
            with self.assertRaises(ValidationError):
                v.validate_positive_int(bad, "N", 500)
        self.assertEqual(v.validate_choice("SIZE", ("name", "size"), "Sort"), "size")
        with self.assertRaises(ValidationError):
            v.validate_choice("colour", ("name", "size"), "Sort")


class TestPathValidators(TempFolderTest):
    def test_directory(self):
        self.assertEqual(v.validate_directory(f'"{self.root}"'), self.root)
        file_path = self.make("a.txt")
        with self.assertRaises(ValidationError):
            v.validate_directory(file_path)
        with self.assertRaises(ValidationError):
            v.validate_directory(self.root / "missing")

    def test_inside_blocks_traversal(self):
        self.assertEqual(v.validate_inside(self.root, "sub/x.txt"), self.root / "sub" / "x.txt")
        for bad in ["../outside.txt", "sub/../../x", str(self.root.parent / "x")]:
            with self.assertRaises(UnsafePathError):
                v.validate_inside(self.root, bad)


if __name__ == "__main__":
    unittest.main()
